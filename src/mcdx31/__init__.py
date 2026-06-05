"""mcdx31: convert Mathcad Prime 4–12 worksheets to Prime 3.1 format."""
from __future__ import annotations

import io
import pathlib
import zipfile
from typing import List

from ._transforms import convert_zip
from ._validate import ValidationResult, validate as _validate

__version__ = "0.1.0"
__all__ = ["convert", "validate_mcdx", "__version__"]


def convert(
    src: pathlib.Path,
    dst: pathlib.Path,
    *,
    verbose: bool = False,
) -> List[str]:
    """
    Convert a Mathcad Prime 4–12 .mcdx file to Prime 3.1 format.

    Parameters
    ----------
    src:     Path to the source .mcdx file.
    dst:     Path for the output .mcdx file (parent directory is created if needed).
    verbose: If True, print each modified ZIP entry name.

    Returns
    -------
    List of ZIP entry names that were modified.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(src) as zin:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            changed = convert_zip(zin, zout, verbose=verbose)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(buf.getvalue())
    return changed


def validate_mcdx(path: pathlib.Path) -> ValidationResult:
    """
    Run post-conversion validation checks on a .mcdx file.

    Returns a ValidationResult with ok=True if all checks pass,
    or ok=False with a list of error strings.
    """
    return _validate(path)
