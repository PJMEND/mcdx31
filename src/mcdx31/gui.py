"""Minimal GUI for mcdx31 — opens file picker, converts, done."""
from __future__ import annotations

import io
import pathlib
import sys
import tkinter as tk
import zipfile
from tkinter import filedialog, messagebox
from typing import List

from ._transforms import convert_zip
from ._validate import validate


def main(argv: List[str] | None = None) -> int:
    root = tk.Tk()
    root.withdraw()

    path = filedialog.askopenfilename(
        title="Select .mcdx file to convert to Prime 3.1",
        filetypes=[("Mathcad files", "*.mcdx"), ("All files", "*.*")],
    )

    if not path:
        return 0

    src = pathlib.Path(path)
    dst = src.parent / (src.stem + "_3x" + src.suffix)

    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(src) as zin:
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                convert_zip(zin, zout)
        dst.write_bytes(buf.getvalue())

        result = validate(dst)
        if result.ok:
            messagebox.showinfo("mcdx31", f"Done.\n\nSaved as:\n{dst}")
        else:
            errs = "\n".join(result.errors)
            messagebox.showwarning("mcdx31", f"Converted with warnings:\n{dst}\n\n{errs}")
    except Exception as exc:
        messagebox.showerror("mcdx31", str(exc))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
