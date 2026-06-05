"""Command-line interface for mcdx31."""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import sys
import tempfile
from typing import List, Tuple

from . import __version__
from ._transforms import convert_zip
from ._validate import validate

import io
import zipfile


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_backup(path: pathlib.Path) -> pathlib.Path:
    """Copy path to path.bak (or path.bak.1, .bak.2, … if .bak already exists)."""
    bak = path.with_suffix(path.suffix + ".bak")
    if bak.exists():
        n = 1
        while True:
            candidate = bak.with_suffix(f".bak.{n}")
            if not candidate.exists():
                bak = candidate
                break
            n += 1
    shutil.copy2(path, bak)
    return bak


def _resolve_output(
    src: pathlib.Path,
    output_dir: pathlib.Path | None,
    suffix: str,
    in_place: bool,
) -> pathlib.Path:
    if in_place:
        return src
    stem = src.stem + suffix
    out_parent = output_dir if output_dir else src.parent
    return out_parent / (stem + src.suffix)


def _collect_files(
    files: List[str],
    batch: pathlib.Path | None,
    recursive: bool,
) -> List[pathlib.Path]:
    result: List[pathlib.Path] = []
    for f in files:
        p = pathlib.Path(f)
        if not p.exists():
            print(f"WARNING: {p} does not exist — skipping", file=sys.stderr)
        else:
            result.append(p)
    if batch is not None:
        pattern = "**/*.mcdx" if recursive else "*.mcdx"
        result.extend(sorted(batch.glob(pattern)))
    return result


def _convert_one(
    src: pathlib.Path,
    dst: pathlib.Path,
    *,
    backup: bool,
    dry_run: bool,
    run_validate: bool,
    verbose: bool,
    quiet: bool,
) -> int:
    """
    Convert src -> dst. Returns:
      0 — success
      1 — validation failure
      2 — exception
    """
    in_place = src == dst

    if dry_run:
        if not quiet:
            print(f"[dry-run] would convert: {src} -> {dst}")
        return 0

    try:
        bak_path = None
        if backup and src.exists():
            bak_path = _make_backup(src)
            if not quiet:
                print(f"  backup: {bak_path.name}")

        buf = io.BytesIO()
        with zipfile.ZipFile(src) as zin:
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                changed = convert_zip(zin, zout, verbose=verbose)

        if in_place:
            # Atomic overwrite via a temp file in the same directory
            fd, tmp_path = tempfile.mkstemp(dir=src.parent, suffix=".mcdx.tmp")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(buf.getvalue())
                os.replace(tmp_path, dst)
            except Exception:
                os.unlink(tmp_path)
                raise
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(buf.getvalue())

        if not quiet:
            print(f"  converted: {src.name} -> {dst}")

        if run_validate:
            result = validate(dst)
            if not result.ok:
                for err in result.errors:
                    print(f"  VALIDATION ERROR: {err}", file=sys.stderr)
                return 1

    except Exception as exc:
        print(f"  ERROR converting {src}: {exc}", file=sys.stderr)
        return 2

    return 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mcdx31",
        description="Convert Mathcad Prime 4–12 .mcdx worksheets to Prime 3.1 format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  mcdx31 sheet.mcdx\n"
            "  mcdx31 sheet.mcdx --output ./converted/\n"
            "  mcdx31 --batch ./templates/ --output ./templates_31/\n"
            "  mcdx31 sheet.mcdx --in-place\n"
            "  mcdx31 --batch . --dry-run\n"
        ),
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="One or more .mcdx files to convert.",
    )
    parser.add_argument(
        "--batch",
        metavar="DIR",
        type=pathlib.Path,
        help="Convert all .mcdx files in DIR.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="With --batch, search subdirectories recursively.",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        type=pathlib.Path,
        help="Write converted files to DIR (default: alongside the source).",
    )
    parser.add_argument(
        "--suffix",
        default="_3x",
        metavar="SUFFIX",
        help="Append SUFFIX to output filename stem (default: _3x). Ignored with --in-place.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the source file (implies --backup).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup even with --in-place (dangerous).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing any files.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip post-conversion validation.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print each modified ZIP entry name.",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress all output except errors.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"mcdx31 {__version__}",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical user interface.",
    )

    args = parser.parse_args(argv)

    if args.gui:
        from .gui import main as gui_main
        return gui_main()

    # --- argument validation ---
    if args.in_place and args.output:
        parser.error("--in-place and --output are mutually exclusive.")
    if args.no_backup and not args.in_place:
        parser.error("--no-backup only makes sense with --in-place.")
    if not args.files and args.batch is None:
        parser.error("Provide at least one FILE or use --batch DIR.")
    if args.batch is not None and not args.batch.is_dir():
        parser.error(f"--batch argument is not a directory: {args.batch}")

    # --- collect source files ---
    sources = _collect_files(args.files, args.batch, args.recursive)
    if not sources:
        print("No .mcdx files found.", file=sys.stderr)
        return 2

    backup = args.in_place and not args.no_backup
    run_validate = not args.no_validate

    worst = 0
    for src in sources:
        dst = _resolve_output(src, args.output, args.suffix, args.in_place)
        code = _convert_one(
            src,
            dst,
            backup=backup,
            dry_run=args.dry_run,
            run_validate=run_validate,
            verbose=args.verbose,
            quiet=args.quiet,
        )
        if code > worst:
            worst = code

    if not args.quiet:
        total = len(sources)
        label = "file" if total == 1 else "files"
        if args.dry_run:
            print(f"Dry run: {total} {label} would be converted.")
        else:
            print(f"Done: {total} {label} processed.")

    return worst


if __name__ == "__main__":
    sys.exit(main())
