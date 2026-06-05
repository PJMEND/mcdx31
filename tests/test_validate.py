"""Unit tests for _validate.py â€” uses synthetic ZIP fixtures."""
from __future__ import annotations

import io
import pathlib
import zipfile

import pytest

from mcdx31._validate import (
    ValidationResult,
    check_app_xml_version,
    check_result_xml,
    check_xaml_packages,
    check_zip_integrity,
    validate,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_inner_pkg(doc: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("Xaml/Document.xaml", doc.encode("utf-8"))
    return buf.getvalue()


def _make_mcdx(
    tmp_path: pathlib.Path,
    app_xml: str = "",
    result_xml: str = "",
    xaml_doc: str = "",
    name: str = "test.mcdx",
) -> pathlib.Path:
    p = tmp_path / name
    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as z:
        if app_xml:
            z.writestr("docProps/app.xml", app_xml)
        if result_xml:
            z.writestr("mathcad/result.xml", result_xml)
        if xaml_doc:
            z.writestr("mathcad/xaml/r1.XamlPackage", _make_inner_pkg(xaml_doc))
    return p


# ---------------------------------------------------------------------------
# check_zip_integrity
# ---------------------------------------------------------------------------

def test_zip_integrity_good_file(tmp_path):
    p = _make_mcdx(tmp_path, app_xml="<x/>")
    assert check_zip_integrity(p) == []


def test_zip_integrity_corrupt_file(tmp_path):
    p = tmp_path / "bad.mcdx"
    p.write_bytes(b"not a zip file at all")
    errors = check_zip_integrity(p)
    assert len(errors) == 1
    assert "corrupt" in errors[0].lower() or "open" in errors[0].lower()


# ---------------------------------------------------------------------------
# check_app_xml_version
# ---------------------------------------------------------------------------

def test_app_xml_correct_version(tmp_path):
    xml = (
        '<properties xmlns="http://schemas.mathsoft.com/extended-properties">'
        "<appVersion>3.1.0.0</appVersion>"
        "<serializationVersion>3.1.0.0</serializationVersion>"
        "</properties>"
    )
    p = _make_mcdx(tmp_path, app_xml=xml)
    assert check_app_xml_version(p) == []


def test_app_xml_wrong_version(tmp_path):
    xml = (
        "<properties>"
        "<appVersion>12.0.0.0</appVersion>"
        "<serializationVersion>12.0.0.0</serializationVersion>"
        "</properties>"
    )
    p = _make_mcdx(tmp_path, app_xml=xml)
    errors = check_app_xml_version(p)
    assert len(errors) == 2
    assert all("3.1.0.0" in e for e in errors)


def test_app_xml_missing_entry(tmp_path):
    p = _make_mcdx(tmp_path, result_xml="<resultsList/>")
    errors = check_app_xml_version(p)
    assert any("Missing" in e for e in errors)


# ---------------------------------------------------------------------------
# check_xaml_packages
# ---------------------------------------------------------------------------

def test_xaml_clean(tmp_path):
    p = _make_mcdx(tmp_path, xaml_doc="<Run>hello</Run>")
    assert check_xaml_packages(p) == []


def test_xaml_style_attribute(tmp_path):
    p = _make_mcdx(tmp_path, xaml_doc='<Run style="x">hello</Run>')
    errors = check_xaml_packages(p)
    assert any("style=" in e for e in errors)


def test_xaml_lang_attribute(tmp_path):
    p = _make_mcdx(tmp_path, xaml_doc='<Run xml:lang="en">hello</Run>')
    errors = check_xaml_packages(p)
    assert any("xml:lang=" in e for e in errors)


def test_xaml_no_packages(tmp_path):
    p = _make_mcdx(tmp_path, app_xml="<x/>")
    assert check_xaml_packages(p) == []


# ---------------------------------------------------------------------------
# check_result_xml
# ---------------------------------------------------------------------------

def test_result_xml_empty(tmp_path):
    xml = '<resultsList xmlns="http://schemas.mathsoft.com/result10"/>'
    p = _make_mcdx(tmp_path, result_xml=xml)
    assert check_result_xml(p) == []


def test_result_xml_with_children(tmp_path):
    xml = '<resultsList xmlns="http://schemas.mathsoft.com/result10"><entry/></resultsList>'
    p = _make_mcdx(tmp_path, result_xml=xml)
    errors = check_result_xml(p)
    assert any("cached result" in e for e in errors)


def test_result_xml_missing(tmp_path):
    p = _make_mcdx(tmp_path, app_xml="<x/>")
    errors = check_result_xml(p)
    assert any("Missing" in e for e in errors)


# ---------------------------------------------------------------------------
# validate() integration
# ---------------------------------------------------------------------------

def test_validate_converted_fixture():
    """The pre-generated 3.1 fixture must pass all checks."""
    p = FIXTURES / "minimal_prime31.mcdx"
    result = validate(p)
    assert result.ok, result.errors


def test_validate_prime12_fixture_fails():
    """The Prime 12 fixture should fail version and XAML checks."""
    p = FIXTURES / "minimal_prime12.mcdx"
    result = validate(p)
    assert not result.ok
    assert len(result.errors) > 0


def test_validate_returns_dataclass(tmp_path):
    xml = (
        '<properties xmlns="http://schemas.mathsoft.com/extended-properties">'
        "<appVersion>3.1.0.0</appVersion>"
        "<serializationVersion>3.1.0.0</serializationVersion>"
        "</properties>"
    )
    result_xml = '<resultsList xmlns="http://schemas.mathsoft.com/result10"/>'
    p = _make_mcdx(tmp_path, app_xml=xml, result_xml=result_xml, xaml_doc="<Run>hi</Run>")
    result = validate(p)
    assert isinstance(result, ValidationResult)

