"""Unit tests for _transforms.py — no filesystem or Mathcad required."""
from __future__ import annotations

import io
import zipfile

import pytest

from mcdx_downgrade._transforms import (
    build_empty_result,
    downgrade_run_attrs,
    downgrade_xaml,
    downgrade_xaml_package,
    downgrade_zip,
    strip_msg_id,
)


# ---------------------------------------------------------------------------
# strip_msg_id
# ---------------------------------------------------------------------------

def test_strip_msg_id_removes_attribute():
    ws = '<worksheet msg-id="NoMessage" xmlns="http://schemas.mathsoft.com/worksheet50">'
    result = strip_msg_id(ws)
    assert 'msg-id=' not in result
    assert 'xmlns=' in result


def test_strip_msg_id_no_false_positive():
    ws = '<worksheet xmlns="http://schemas.mathsoft.com/worksheet50">'
    assert strip_msg_id(ws) == ws


def test_strip_msg_id_only_removes_first():
    ws = '<worksheet msg-id="A"><inner msg-id="B"/>'
    result = strip_msg_id(ws)
    assert result.count('msg-id=') == 1
    assert 'msg-id="B"' in result


# ---------------------------------------------------------------------------
# downgrade_run_attrs
# ---------------------------------------------------------------------------

def test_downgrade_run_attrs_strips_style():
    result = downgrade_run_attrs(' style="font-size:10pt"')
    assert 'style=' not in result


def test_downgrade_run_attrs_strips_xml_lang():
    result = downgrade_run_attrs(' xml:lang="en-US"')
    assert 'xml:lang=' not in result


def test_downgrade_run_attrs_preserves_other():
    result = downgrade_run_attrs(' FontFamily="Arial" style="x" FontSize="12"')
    assert 'FontFamily="Arial"' in result
    assert 'FontSize="12"' in result
    assert 'style=' not in result


def test_downgrade_run_attrs_empty():
    assert downgrade_run_attrs("") == ""


# ---------------------------------------------------------------------------
# downgrade_xaml
# ---------------------------------------------------------------------------

def test_downgrade_xaml_strips_run_attrs():
    doc = '<Run style="font-size:10pt" xml:lang="en-US">hello</Run>'
    out = downgrade_xaml(doc)
    assert out == "<Run>hello</Run>"


def test_downgrade_xaml_preserves_non_run():
    doc = '<Paragraph style="normal"><Run>text</Run></Paragraph>'
    out = downgrade_xaml(doc)
    assert '<Paragraph style="normal">' in out
    assert "<Run>text</Run>" in out


def test_downgrade_xaml_multiple_runs():
    doc = (
        '<Run style="a" xml:lang="en">one</Run>'
        '<Run xml:lang="fr">two</Run>'
        "<Run>three</Run>"
    )
    out = downgrade_xaml(doc)
    assert out.count('<Run>') == 3
    assert 'style=' not in out
    assert 'xml:lang=' not in out


# ---------------------------------------------------------------------------
# downgrade_xaml_package
# ---------------------------------------------------------------------------

def _make_xaml_pkg(doc: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("Xaml/Document.xaml", doc.encode("utf-8"))
        z.writestr("other.xml", b"<other/>")
    return buf.getvalue()


def test_downgrade_xaml_package_strips_run_attrs():
    pkg = _make_xaml_pkg('<Run style="x" xml:lang="en">hi</Run>')
    out = downgrade_xaml_package(pkg)
    with zipfile.ZipFile(io.BytesIO(out)) as z:
        doc = z.read("Xaml/Document.xaml").decode()
    assert 'style=' not in doc
    assert 'xml:lang=' not in doc
    assert "<Run>hi</Run>" in doc


def test_downgrade_xaml_package_preserves_other_entries():
    pkg = _make_xaml_pkg("<Run>text</Run>")
    out = downgrade_xaml_package(pkg)
    with zipfile.ZipFile(io.BytesIO(out)) as z:
        assert z.read("other.xml") == b"<other/>"


# ---------------------------------------------------------------------------
# build_empty_result
# ---------------------------------------------------------------------------

def test_build_empty_result_preserves_namespaces():
    orig = (
        '<resultsList xmlns:ml="http://schemas.mathsoft.com/math50"'
        ' xmlns="http://schemas.mathsoft.com/result10">'
        "<entry/>"
        "</resultsList>"
    )
    result = build_empty_result(orig).decode()
    assert 'xmlns:ml=' in result
    assert '<resultsList' in result
    # Must be empty — no child elements
    assert "<entry" not in result


def test_build_empty_result_fallback_when_no_match():
    result = build_empty_result("").decode()
    assert "<resultsList" in result
    assert 'xmlns=' in result


# ---------------------------------------------------------------------------
# downgrade_zip (integration of all transforms)
# ---------------------------------------------------------------------------

def _make_prime12_zip() -> bytes:
    """Build a minimal Prime 12 .mcdx bytes for testing downgrade_zip."""
    inner_xaml = _make_xaml_pkg('<Run style="x" xml:lang="en">text</Run>')

    app_xml = (
        '<properties xmlns="http://schemas.mathsoft.com/extended-properties">'
        "<appVersion>12.0.0.0</appVersion>"
        "<serializationVersion>12.0.0.0</serializationVersion>"
        "</properties>"
    )
    worksheet_xml = '<worksheet msg-id="NoMessage" xmlns="http://schemas.mathsoft.com/worksheet50"/>'
    calc_xml = '<calculation xmlns="http://schemas.ptc.com/mathcad/settings/calculation10"><symbolicEngine /></calculation>'
    result_xml = '<resultsList xmlns="http://schemas.mathsoft.com/result10"><entry/></resultsList>'

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("docProps/app.xml", app_xml)
        z.writestr("mathcad/worksheet.xml", worksheet_xml)
        z.writestr("mathcad/settings/calculation.xml", calc_xml)
        z.writestr("mathcad/result.xml", result_xml)
        z.writestr("mathcad/xaml/r1.XamlPackage", inner_xaml)
        z.writestr("mathcad/integration.xml", "<integration/>")
    return buf.getvalue()


def test_downgrade_zip_modifies_expected_entries():
    src_bytes = _make_prime12_zip()
    out_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src_bytes)) as zin:
        with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            changed = downgrade_zip(zin, zout)

    assert "docProps/app.xml" in changed
    assert "mathcad/settings/calculation.xml" in changed
    assert "mathcad/result.xml" in changed


def test_downgrade_zip_preserves_unrelated_entries():
    src_bytes = _make_prime12_zip()
    out_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src_bytes)) as zin:
        with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            downgrade_zip(zin, zout)

    with zipfile.ZipFile(out_buf) as z:
        assert z.read("mathcad/integration.xml") == b"<integration/>"


def test_downgrade_zip_app_xml_contains_31():
    src_bytes = _make_prime12_zip()
    out_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src_bytes)) as zin:
        with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            downgrade_zip(zin, zout)

    with zipfile.ZipFile(out_buf) as z:
        app = z.read("docProps/app.xml").decode()
    assert "3.1.0.0" in app


def test_downgrade_zip_result_is_empty():
    src_bytes = _make_prime12_zip()
    out_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src_bytes)) as zin:
        with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            downgrade_zip(zin, zout)

    with zipfile.ZipFile(out_buf) as z:
        result = z.read("mathcad/result.xml").decode()
    assert "<entry" not in result


def test_downgrade_zip_worksheet_no_msg_id():
    src_bytes = _make_prime12_zip()
    out_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src_bytes)) as zin:
        with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            downgrade_zip(zin, zout)

    with zipfile.ZipFile(out_buf) as z:
        ws = z.read("mathcad/worksheet.xml").decode()
    assert 'msg-id=' not in ws
