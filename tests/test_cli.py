"""Integration tests for cli.py â€” exercises the full conversion pipeline."""
from __future__ import annotations

import io
import pathlib
import shutil
import sys
import zipfile

import pytest

from mcdx31.cli import main

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SRC = FIXTURES / "minimal_prime12.mcdx"


def _copy_to(src: pathlib.Path, dest_dir: pathlib.Path) -> pathlib.Path:
    dst = dest_dir / src.name
    shutil.copy(src, dst)
    return dst


# ---------------------------------------------------------------------------
# Single-file conversion
# ---------------------------------------------------------------------------

def test_single_file_default_suffix(tmp_path):
    src = _copy_to(SRC, tmp_path)
    code = main([str(src)])
    assert code == 0
    out = tmp_path / "minimal_prime12_3x.mcdx"
    assert out.exists()
    assert src.exists()  # source not touched


def test_single_file_custom_output_dir(tmp_path):
    src = _copy_to(SRC, tmp_path)
    out_dir = tmp_path / "out"
    code = main([str(src), "--output", str(out_dir)])
    assert code == 0
    assert (out_dir / "minimal_prime12_3x.mcdx").exists()


def test_single_file_custom_suffix(tmp_path):
    src = _copy_to(SRC, tmp_path)
    code = main([str(src), "--suffix", "_v31"])
    assert code == 0
    assert (tmp_path / "minimal_prime12_v31.mcdx").exists()


# ---------------------------------------------------------------------------
# In-place conversion
# ---------------------------------------------------------------------------

def test_in_place_creates_backup(tmp_path):
    src = _copy_to(SRC, tmp_path)
    code = main([str(src), "--in-place"])
    assert code == 0
    assert src.exists()
    bak = tmp_path / "minimal_prime12.mcdx.bak"
    assert bak.exists()


def test_in_place_no_backup(tmp_path):
    src = _copy_to(SRC, tmp_path)
    code = main([str(src), "--in-place", "--no-backup"])
    assert code == 0
    assert src.exists()
    bak = tmp_path / "minimal_prime12.mcdx.bak"
    assert not bak.exists()


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

def test_dry_run_writes_nothing(tmp_path):
    src = _copy_to(SRC, tmp_path)
    code = main([str(src), "--dry-run"])
    assert code == 0
    out = tmp_path / "minimal_prime12_3x.mcdx"
    assert not out.exists()


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

def test_batch_converts_all(tmp_path):
    # Put two copies of the fixture in a batch dir
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    shutil.copy(SRC, batch_dir / "a.mcdx")
    shutil.copy(SRC, batch_dir / "b.mcdx")

    out_dir = tmp_path / "out"
    code = main(["--batch", str(batch_dir), "--output", str(out_dir)])
    assert code == 0
    assert (out_dir / "a_3x.mcdx").exists()
    assert (out_dir / "b_3x.mcdx").exists()


def test_batch_recursive(tmp_path):
    batch_dir = tmp_path / "batch"
    sub = batch_dir / "sub"
    sub.mkdir(parents=True)
    shutil.copy(SRC, sub / "deep.mcdx")

    out_dir = tmp_path / "out"
    code = main(["--batch", str(batch_dir), "--output", str(out_dir), "--recursive"])
    assert code == 0
    assert any(out_dir.rglob("deep_3x.mcdx"))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_no_validate_flag_skips_check(tmp_path):
    src = _copy_to(SRC, tmp_path)
    code = main([str(src), "--no-validate"])
    assert code == 0


def test_output_passes_validation(tmp_path):
    src = _copy_to(SRC, tmp_path)
    code = main([str(src)])
    assert code == 0  # validation is on by default and should pass


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_nonexistent_file_skipped(tmp_path):
    code = main([str(tmp_path / "does_not_exist.mcdx")])
    # No files to convert â†’ exit 2
    assert code == 2


def test_incompatible_flags_in_place_and_output(tmp_path):
    src = _copy_to(SRC, tmp_path)
    with pytest.raises(SystemExit):
        main([str(src), "--in-place", "--output", str(tmp_path)])


def test_no_backup_without_in_place(tmp_path):
    src = _copy_to(SRC, tmp_path)
    with pytest.raises(SystemExit):
        main([str(src), "--no-backup"])


# ---------------------------------------------------------------------------
# CLI version flag
# ---------------------------------------------------------------------------

def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "0.1.0" in captured.out

