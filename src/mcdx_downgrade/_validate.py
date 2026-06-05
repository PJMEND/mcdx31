"""Post-conversion validation checks for downgraded .mcdx files."""
from __future__ import annotations

import io
import pathlib
import re
import zipfile
from dataclasses import dataclass, field
from typing import List


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str] = field(default_factory=list)


def check_zip_integrity(path: pathlib.Path) -> List[str]:
    """Open the outer ZIP and test every member CRC. Returns list of error strings."""
    errors: List[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad is not None:
                errors.append(f"ZIP CRC error on entry: {bad}")
    except zipfile.BadZipFile as exc:
        errors.append(f"Outer ZIP is corrupt: {exc}")
    except Exception as exc:
        errors.append(f"Could not open file: {exc}")
    return errors


def check_app_xml_version(path: pathlib.Path) -> List[str]:
    """Confirm appVersion and serializationVersion are both 3.1.0.0."""
    errors: List[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            if "docProps/app.xml" not in z.namelist():
                errors.append("Missing docProps/app.xml")
                return errors
            xml = z.read("docProps/app.xml").decode("utf-8")
    except Exception as exc:
        errors.append(f"Cannot read docProps/app.xml: {exc}")
        return errors

    for tag in ("appVersion", "serializationVersion"):
        m = re.search(rf"<{tag}[^>]*>([^<]+)</{tag}>", xml)
        if not m:
            errors.append(f"Tag <{tag}> not found in docProps/app.xml")
        elif m.group(1).strip() != "3.1.0.0":
            errors.append(
                f"Expected {tag}=3.1.0.0, got {m.group(1).strip()!r}"
            )
    return errors


def check_xaml_packages(path: pathlib.Path) -> List[str]:
    """
    For each *.XamlPackage entry:
      - Verify inner ZIP CRC
      - Confirm Document.xaml has no style= or xml:lang= on <Run> elements
    """
    errors: List[str] = []
    try:
        with zipfile.ZipFile(path) as outer:
            pkgs = [n for n in outer.namelist() if n.endswith(".XamlPackage")]
            for pkg_name in pkgs:
                pkg_bytes = outer.read(pkg_name)
                try:
                    inner = zipfile.ZipFile(io.BytesIO(pkg_bytes))
                    bad = inner.testzip()
                    if bad is not None:
                        errors.append(f"{pkg_name}: inner ZIP CRC error on {bad}")
                        continue
                    if "Xaml/Document.xaml" in inner.namelist():
                        doc = inner.read("Xaml/Document.xaml").decode("utf-8")
                        if re.search(r'<Run[^>]+style="', doc):
                            errors.append(f"{pkg_name}: <Run> still has style= attribute")
                        if re.search(r'<Run[^>]+xml:lang="', doc):
                            errors.append(f"{pkg_name}: <Run> still has xml:lang= attribute")
                except zipfile.BadZipFile as exc:
                    errors.append(f"{pkg_name}: inner ZIP corrupt: {exc}")
    except Exception as exc:
        errors.append(f"Cannot read XamlPackages: {exc}")
    return errors


def check_result_xml(path: pathlib.Path) -> List[str]:
    """Verify mathcad/result.xml is present and is an empty resultsList."""
    errors: List[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            if "mathcad/result.xml" not in z.namelist():
                errors.append("Missing mathcad/result.xml")
                return errors
            xml = z.read("mathcad/result.xml").decode("utf-8").strip()
    except Exception as exc:
        errors.append(f"Cannot read mathcad/result.xml: {exc}")
        return errors

    # Must be a self-closing or immediately-closed resultsList with no children
    if not re.search(r"<resultsList[^>]*/?>", xml):
        errors.append("mathcad/result.xml does not contain a valid resultsList element")
    elif re.search(r"<resultsList[^>]*><", xml):
        errors.append("mathcad/result.xml still contains cached result entries")
    return errors


def validate(path: pathlib.Path) -> ValidationResult:
    """Run all post-conversion checks and return a ValidationResult."""
    errors: List[str] = []
    errors.extend(check_zip_integrity(path))
    if not errors:
        errors.extend(check_app_xml_version(path))
        errors.extend(check_xaml_packages(path))
        errors.extend(check_result_xml(path))
    return ValidationResult(ok=len(errors) == 0, errors=errors)
