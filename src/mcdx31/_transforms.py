"""Pure XML/ZIP transform functions — no filesystem I/O."""
from __future__ import annotations

import io
import re
import zipfile
from typing import List

from ._constants import APP_XML_31, CALC_XML_31, PRES_XML_31


def strip_msg_id(ws_xml: str) -> str:
    """Remove msg-id="..." attribute from the <worksheet> root element."""
    return re.sub(r'\s+msg-id="[^"]*"', "", ws_xml, count=1)


def downgrade_run_attrs(tag_attrs: str) -> str:
    """Strip style="..." and xml:lang="..." from a <Run> element's attribute string."""
    tag_attrs = re.sub(r'\s+style="[^"]*"', "", tag_attrs)
    tag_attrs = re.sub(r'\s+xml:lang="[^"]*"', "", tag_attrs)
    return tag_attrs


def downgrade_xaml(doc: str) -> str:
    """Remove Prime 4+ Run attributes that the Prime 3.1 FlowDocument deserializer rejects."""
    return re.sub(
        r"<Run([^>]*)>",
        lambda m: "<Run" + downgrade_run_attrs(m.group(1)) + ">",
        doc,
    )


def downgrade_xaml_package(pkg_bytes: bytes) -> bytes:
    """Rewrite a XamlPackage (ZIP-in-ZIP) with 3.1-compatible Document.xaml."""
    src = zipfile.ZipFile(io.BytesIO(pkg_bytes))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            content = src.read(info.filename)
            if info.filename == "Xaml/Document.xaml":
                content = downgrade_xaml(content.decode("utf-8")).encode("utf-8")
            dst.writestr(info, content)
    return buf.getvalue()


def build_empty_result(orig_result_xml: str) -> bytes:
    """Return a minimal empty resultsList, preserving namespace declarations from the original."""
    ns_match = re.search(r"<resultsList([^>]*)>", orig_result_xml)
    ns_attrs = ns_match.group(1) if ns_match else (
        ' xmlns:ml="http://schemas.mathsoft.com/math50"'
        ' xmlns:u="http://schemas.mathsoft.com/units10"'
        ' xmlns="http://schemas.mathsoft.com/result10"'
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f"<resultsList{ns_attrs}/>"
    ).encode("utf-8")


def downgrade_zip(
    zin: zipfile.ZipFile,
    zout: zipfile.ZipFile,
    *,
    verbose: bool = False,
) -> List[str]:
    """
    Read every entry from zin, apply 3.1 transforms, write to zout.
    Returns the list of entry names that were modified.
    """
    changed: List[str] = []

    orig_result = (
        zin.read("mathcad/result.xml").decode("utf-8")
        if "mathcad/result.xml" in zin.namelist()
        else ""
    )
    empty_result = build_empty_result(orig_result)

    ws_xml = zin.read("mathcad/worksheet.xml").decode("utf-8")
    patched_ws = strip_msg_id(ws_xml)
    if patched_ws != ws_xml:
        changed.append("mathcad/worksheet.xml")

    for info in zin.infolist():
        name = info.filename

        if name == "docProps/app.xml":
            zout.writestr(info, APP_XML_31.encode("utf-8"))
            changed.append(name)

        elif name == "mathcad/worksheet.xml":
            zout.writestr(info, patched_ws.encode("utf-8"))

        elif name == "mathcad/result.xml":
            zout.writestr(info, empty_result)
            changed.append(name)

        elif name == "mathcad/settings/calculation.xml":
            zout.writestr(info, CALC_XML_31.encode("utf-8"))
            changed.append(name)

        elif name == "mathcad/settings/presentation.xml":
            zout.writestr(info, PRES_XML_31.encode("utf-8"))
            changed.append(name)

        elif name.startswith("mathcad/xaml/") and name.endswith(".XamlPackage"):
            original = zin.read(name)
            patched = downgrade_xaml_package(original)
            zout.writestr(info, patched)
            if patched != original:
                changed.append(name)

        else:
            zout.writestr(info, zin.read(name))

    if verbose:
        for entry in changed:
            print(f"  patched: {entry}")

    return changed
