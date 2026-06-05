"""
Generate synthetic .mcdx fixture files for the test suite.

Run once to (re)create the committed binary fixtures:
    python tests/make_fixtures.py
"""
from __future__ import annotations

import io
import pathlib
import zipfile

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _make_inner_xaml_package(has_prime12_attrs: bool = True) -> bytes:
    """Build a minimal XamlPackage (ZIP-in-ZIP)."""
    run_tag = (
        '<Run style="font-size:10pt" xml:lang="en-US">hello</Run>'
        if has_prime12_attrs
        else "<Run>hello</Run>"
    )
    doc_xaml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<FlowDocument>"
        f"<Paragraph>{run_tag}</Paragraph>"
        "</FlowDocument>"
    ).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("Xaml/Document.xaml", doc_xaml)
    return buf.getvalue()


def make_prime12_mcdx(path: pathlib.Path) -> None:
    """Create a minimal Prime 12 .mcdx file (the 'before' fixture)."""
    app_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<properties xmlns="http://schemas.mathsoft.com/extended-properties">'
        "<appVersion>12.0.0.0</appVersion>"
        "<serializationVersion>12.0.0.0</serializationVersion>"
        "</properties>"
    ).encode("utf-8")

    worksheet_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<worksheet msg-id="NoMessage" xmlns="http://schemas.mathsoft.com/worksheet50">'
        "</worksheet>"
    ).encode("utf-8")

    calc_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<calculation xmlns="http://schemas.ptc.com/mathcad/settings/calculation10">'
        "<symbolicEngine enabled=\"true\" />"
        "</calculation>"
    ).encode("utf-8")

    pres_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<presentation xmlns="http://schemas.ptc.com/mathcad/settings/presentation10">'
        '<pageModel paper-code="A4" orientation="Portrait" newer-attr="yes" />'
        "</presentation>"
    ).encode("utf-8")

    result_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<resultsList xmlns:ml="http://schemas.mathsoft.com/math50"'
        ' xmlns:u="http://schemas.mathsoft.com/units10"'
        ' xmlns="http://schemas.mathsoft.com/result10">'
        "<someResult/>"
        "</resultsList>"
    ).encode("utf-8")

    xaml_pkg = _make_inner_xaml_package(has_prime12_attrs=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("docProps/app.xml", app_xml)
        z.writestr("mathcad/worksheet.xml", worksheet_xml)
        z.writestr("mathcad/settings/calculation.xml", calc_xml)
        z.writestr("mathcad/settings/presentation.xml", pres_xml)
        z.writestr("mathcad/result.xml", result_xml)
        z.writestr("mathcad/xaml/region1.XamlPackage", xaml_pkg)
        z.writestr("mathcad/integration.xml", b"<integration/>")

    print(f"Written: {path}")


def make_prime31_mcdx(path: pathlib.Path) -> None:
    """Create a minimal Prime 3.1 .mcdx file (the 'after' fixture)."""
    from sys import path as _syspath
    import os

    # Import the package under src/
    _root = pathlib.Path(__file__).parent.parent
    _src = str(_root / "src")
    if _src not in _syspath:
        _syspath.insert(0, _src)

    from mcdx31._transforms import convert_zip

    src_path = FIXTURES / "minimal_prime12.mcdx"
    buf = io.BytesIO()
    with zipfile.ZipFile(src_path) as zin:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            convert_zip(zin, zout)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())
    print(f"Written: {path}")


if __name__ == "__main__":
    make_prime12_mcdx(FIXTURES / "minimal_prime12.mcdx")
    make_prime31_mcdx(FIXTURES / "minimal_prime31.mcdx")
    print("Done.")

