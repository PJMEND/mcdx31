"""Standalone Tkinter GUI for mcdx31."""
from __future__ import annotations

import io
import pathlib
import queue
import sys
import threading
import tkinter as tk
import zipfile
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import List

from . import __version__
from ._transforms import convert_zip
from ._validate import validate


# ---------------------------------------------------------------------------
# Queue-based stdout redirect (thread-safe log append)
# ---------------------------------------------------------------------------

class _QueueWriter:
    def __init__(self, q: queue.Queue):
        self.q = q

    def write(self, s: str):
        if s:
            self.q.put(s)

    def flush(self):
        pass


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class DowngradeApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(f"mcdx31  v{__version__}")
        self.resizable(True, True)
        self.minsize(620, 460)
        self.geometry("780x560")

        self._log_queue: queue.Queue = queue.Queue()
        self._running = False

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}

        # ---- Title ----
        hdr = ttk.Label(
            self,
            text="Mathcad Prime .mcdx → 3.1 Converter",
            font=("TkDefaultFont", 11, "bold"),
        )
        hdr.pack(anchor="w", padx=12, pady=(12, 2))
        ttk.Label(
            self,
            text=(
                "Strips Prime 4–12 XamlPackage attributes, clears cached results,\n"
                "and patches version stamps so Prime 3.1 can open the file."
            ),
            foreground="gray",
            font=("TkDefaultFont", 8),
        ).pack(anchor="w", padx=14, pady=(0, 8))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=2)

        # ---- Mode selector ----
        mode_frame = ttk.LabelFrame(self, text="Mode", padding=6)
        mode_frame.pack(fill="x", padx=10, pady=4)

        self._mode_var = tk.StringVar(value="single")
        ttk.Radiobutton(
            mode_frame, text="Single file",
            variable=self._mode_var, value="single",
            command=self._on_mode_changed,
        ).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(
            mode_frame, text="Batch folder",
            variable=self._mode_var, value="batch",
            command=self._on_mode_changed,
        ).pack(side="left")

        # ---- Input row ----
        self._in_frame = ttk.Frame(self)
        self._in_frame.pack(fill="x", padx=10, pady=3)
        ttk.Label(self._in_frame, text="Input .mcdx:", width=14, anchor="w").pack(side="left")
        self._in_var = tk.StringVar()
        self._in_entry = ttk.Entry(self._in_frame, textvariable=self._in_var)
        self._in_entry.pack(side="left", padx=(4, 4), fill="x", expand=True)
        self._in_btn = ttk.Button(
            self._in_frame, text="Browse…", command=self._browse_input)
        self._in_btn.pack(side="left")
        self._in_var.trace_add("write", self._on_input_changed)

        # ---- Output row ----
        out_frame = ttk.Frame(self)
        out_frame.pack(fill="x", padx=10, pady=3)
        self._out_label = ttk.Label(out_frame, text="Output .mcdx:", width=14, anchor="w")
        self._out_label.pack(side="left")
        self._out_var = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self._out_var).pack(
            side="left", padx=(4, 4), fill="x", expand=True)
        ttk.Button(out_frame, text="Browse…", command=self._browse_output).pack(side="left")

        # ---- Options ----
        opt_frame = ttk.LabelFrame(self, text="Options", padding=6)
        opt_frame.pack(fill="x", padx=10, pady=4)

        self._in_place_var = tk.BooleanVar(value=False)
        self._backup_var = tk.BooleanVar(value=True)
        self._validate_var = tk.BooleanVar(value=True)
        self._verbose_var = tk.BooleanVar(value=False)
        self._recursive_var = tk.BooleanVar(value=False)

        self._in_place_cb = ttk.Checkbutton(
            opt_frame, text="In-place (overwrite source)",
            variable=self._in_place_var, command=self._on_in_place_changed)
        self._in_place_cb.grid(row=0, column=0, sticky="w", padx=(0, 16))

        self._backup_cb = ttk.Checkbutton(
            opt_frame, text="Create .bak backup",
            variable=self._backup_var)
        self._backup_cb.grid(row=0, column=1, sticky="w", padx=(0, 16))

        self._validate_cb = ttk.Checkbutton(
            opt_frame, text="Validate after conversion",
            variable=self._validate_var)
        self._validate_cb.grid(row=0, column=2, sticky="w", padx=(0, 16))

        self._verbose_cb = ttk.Checkbutton(
            opt_frame, text="Verbose output",
            variable=self._verbose_var)
        self._verbose_cb.grid(row=1, column=0, sticky="w", padx=(0, 16))

        self._recursive_cb = ttk.Checkbutton(
            opt_frame, text="Recursive (batch only)",
            variable=self._recursive_var)
        self._recursive_cb.grid(row=1, column=1, sticky="w")

        # ---- Convert button ----
        self._convert_btn = ttk.Button(
            self, text="Convert to Prime 3.1", command=self._on_convert)
        self._convert_btn.pack(pady=(6, 4))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=4)

        # ---- Log ----
        ttk.Label(self, text="Log:", anchor="w").pack(anchor="w", padx=12)
        self._log = scrolledtext.ScrolledText(
            self, height=10, state="disabled", font=("Consolas", 9))
        self._log.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self._on_mode_changed()

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _on_mode_changed(self):
        mode = self._mode_var.get()
        if mode == "single":
            self._in_entry.config(state="normal")
            self._in_btn.config(text="Browse…")
            self._out_label.config(text="Output .mcdx:")
            self._in_place_cb.config(state="normal")
            self._recursive_cb.config(state="disabled")
        else:
            self._in_entry.config(state="normal")
            self._in_btn.config(text="Browse folder…")
            self._out_label.config(text="Output folder:")
            self._in_place_cb.config(state="disabled")
            self._recursive_cb.config(state="normal")

    def _on_in_place_changed(self):
        if self._in_place_var.get():
            self._out_var.set("")
            self._backup_var.set(True)

    # ------------------------------------------------------------------
    # Browse
    # ------------------------------------------------------------------

    def _browse_input(self):
        if self._mode_var.get() == "single":
            path = filedialog.askopenfilename(
                title="Select .mcdx to convert",
                filetypes=[("Mathcad files", "*.mcdx"), ("All files", "*.*")],
            )
            if path:
                self._in_var.set(path)
        else:
            path = filedialog.askdirectory(title="Select folder with .mcdx files")
            if path:
                self._in_var.set(path)

    def _browse_output(self):
        if self._mode_var.get() == "single":
            path = filedialog.asksaveasfilename(
                title="Save converted file as…",
                defaultextension=".mcdx",
                filetypes=[("Mathcad files", "*.mcdx")],
            )
        else:
            path = filedialog.askdirectory(title="Select output folder")
        if path:
            self._out_var.set(path)

    def _on_input_changed(self, *_):
        if self._mode_var.get() != "single":
            return
        src = self._in_var.get().strip()
        if src and not self._in_place_var.get():
            p = pathlib.Path(src)
            self._out_var.set(str(p.parent / (p.stem + "_3x" + p.suffix)))

    # ------------------------------------------------------------------
    # Convert
    # ------------------------------------------------------------------

    def _on_convert(self):
        src = self._in_var.get().strip()
        dst = self._out_var.get().strip()
        mode = self._mode_var.get()
        in_place = self._in_place_var.get() and mode == "single"
        backup = self._backup_var.get()
        run_validate = self._validate_var.get()
        verbose = self._verbose_var.get()
        recursive = self._recursive_var.get()

        if not src:
            messagebox.showerror("No input", "Select a source file or folder.")
            return

        if mode == "single":
            src_path = pathlib.Path(src)
            if not src_path.exists():
                messagebox.showerror("Not found", f"File not found:\n{src}")
                return
            if not in_place and not dst:
                messagebox.showerror("No output", "Set an output path.")
                return
            dst_path = src_path if in_place else pathlib.Path(dst)
            jobs = [(src_path, dst_path)]
        else:
            batch_dir = pathlib.Path(src)
            if not batch_dir.is_dir():
                messagebox.showerror("Not a folder", f"Not a directory:\n{src}")
                return
            pattern = "**/*.mcdx" if recursive else "*.mcdx"
            sources = sorted(batch_dir.glob(pattern))
            if not sources:
                messagebox.showinfo("Nothing to convert",
                                    "No .mcdx files found in the selected folder.")
                return
            out_dir = pathlib.Path(dst) if dst else batch_dir
            jobs = [
                (s, out_dir / (s.stem + "_3x" + s.suffix)) for s in sources
            ]

        self._convert_btn.config(state="disabled")
        self._log.config(state="normal")
        self._log.delete("1.0", tk.END)
        self._log.config(state="disabled")
        self._running = True

        q = self._log_queue

        def _thread():
            old_stdout = sys.stdout
            sys.stdout = _QueueWriter(q)
            errors = 0
            try:
                for src_p, dst_p in jobs:
                    try:
                        _do_convert(
                            src_p, dst_p,
                            backup=backup and (src_p == dst_p),
                            run_validate=run_validate,
                            verbose=verbose,
                        )
                    except Exception as exc:
                        q.put(f"ERROR {src_p.name}: {exc}\n")
                        errors += 1
            finally:
                sys.stdout = old_stdout
                q.put(None)

        threading.Thread(target=_thread, daemon=True).start()
        self.after(80, self._poll_log)

    # ------------------------------------------------------------------
    # Log polling
    # ------------------------------------------------------------------

    def _poll_log(self):
        while True:
            try:
                msg = self._log_queue.get_nowait()
            except queue.Empty:
                break
            if msg is None:
                self._convert_btn.config(state="normal")
                self._running = False
                return
            self._log.config(state="normal")
            self._log.insert(tk.END, msg)
            self._log.see(tk.END)
            self._log.config(state="disabled")
        self.after(80, self._poll_log)


# ---------------------------------------------------------------------------
# Conversion worker (called from background thread)
# ---------------------------------------------------------------------------

def _do_convert(
    src: pathlib.Path,
    dst: pathlib.Path,
    *,
    backup: bool,
    run_validate: bool,
    verbose: bool,
) -> None:
    import shutil
    import os
    import tempfile

    if backup and src.exists():
        bak = src.with_suffix(src.suffix + ".bak")
        shutil.copy2(src, bak)
        print(f"  backup: {bak.name}")

    buf = io.BytesIO()
    with zipfile.ZipFile(src) as zin:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            changed = convert_zip(zin, zout, verbose=verbose)

    in_place = src == dst
    if in_place:
        fd, tmp = tempfile.mkstemp(dir=src.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(buf.getvalue())
            os.replace(tmp, dst)
        except Exception:
            os.unlink(tmp)
            raise
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(buf.getvalue())

    print(f"  converted: {src.name} -> {dst.name}  ({len(changed)} entries patched)")

    if run_validate:
        result = validate(dst)
        if result.ok:
            print("  validation: OK")
        else:
            for err in result.errors:
                print(f"  VALIDATION ERROR: {err}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> int:
    app = DowngradeApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
