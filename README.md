# mcdx31

Convert Mathcad Prime 4–12 worksheets to Prime 3.1 format.

**mcdx31** lets you open `.mcdx` files created in any version of Mathcad Prime/Express (4 through 12) in Prime 3.1 — useful when you need compatibility with an older Mathcad installation, when sharing calculations with colleagues or clients who are still running Prime 3.1, or when a project requires delivery in a specific legacy format.

---

## What it changes

Six targeted modifications are applied to each file:

1. **`docProps/app.xml`** — Sets `appVersion` and `serializationVersion` to `3.1.0.0` and resets all schema property versions to the 3.1 baseline.
2. **`mathcad/worksheet.xml`** — Removes the `msg-id="NoMessage"` attribute from the root element (not present in the 3.1 schema).
3. **`mathcad/settings/calculation.xml`** — Replaces the entire file with the 3.1 baseline, stripping features absent in 3.1: `symbolicEngine`, `bin-oct-hex-mode`, `customUnitSystem`.
4. **`mathcad/settings/presentation.xml`** — Replaces the entire file with the 3.1 baseline (corrects font references, removes newer page attributes, trims extra `textStyle` entries).
5. **`mathcad/xaml/*.XamlPackage`** — Strips `style="..."` and `xml:lang="..."` from `<Run>` elements in each text region's `Document.xaml`. These attributes were added in Prime 4+ and cause the 3.1 FlowDocument deserializer to reject the file.
6. **`mathcad/result.xml`** — Cleared to prevent stale cached results from causing errors on first open.

## What it does NOT do

- Does **not** re-enable features absent in 3.1 (symbolic engine, custom unit systems, hex/oct/bin display mode).
- Does **not** guarantee every calculation will re-evaluate correctly — some formulas may use functions or operators introduced after Prime 3.1.
- Does **not** convert legacy `.mcd` (Prime 1/2) or `.xmcd` files — only `.mcdx` (Prime 3+).

---

## Requirements

- Python 3.8 or later
- No external dependencies — pure standard library

---

## Installation

```bash
# From PyPI (once published)
pip install mcdx31

# From GitHub
pip install git+https://github.com/PJMEND/mcdx31.git

# Run without installing
python -m mcdx_downgrade input.mcdx
```

---

## Usage

### Single file

```bash
mcdx31 mysheet.mcdx
# Writes mysheet_3x.mcdx alongside the source
```

```bash
mcdx31 mysheet.mcdx --output ./converted/
# Writes ./converted/mysheet_3x.mcdx
```

### Batch conversion

```bash
mcdx31 --batch ./templates/
# Converts every .mcdx in templates/, writes *_3x.mcdx next to each source

mcdx31 --batch ./templates/ --output ./templates_31/ --recursive
# Converts all .mcdx files recursively, mirroring structure into templates_31/
```

### In-place (with automatic backup)

```bash
mcdx31 mysheet.mcdx --in-place
# Overwrites mysheet.mcdx; saves original as mysheet.mcdx.bak
```

### Other options

```bash
mcdx31 --batch . --dry-run        # preview without writing
mcdx31 mysheet.mcdx --verbose     # list every patched ZIP entry
mcdx31 mysheet.mcdx --no-validate # skip post-conversion checks
mcdx31 --version
mcdx31 --help
```

### GUI

```bash
mcdx31-gui
# or
mcdx31 --gui
```

Opens a simple window where you can browse for files or folders, set options, and see conversion output in a scrollable log.

---

## Python API

```python
from pathlib import Path
from mcdx_downgrade import downgrade, validate_mcdx

changed = downgrade(Path("mysheet.mcdx"), Path("mysheet_3x.mcdx"), verbose=True)
print("Modified entries:", changed)

result = validate_mcdx(Path("mysheet_3x.mcdx"))
if result.ok:
    print("Validation passed")
else:
    for err in result.errors:
        print("ERROR:", err)
```

---

## Background

Mathcad Prime `.mcdx` files are ZIP archives containing XML files. When PTC releases new Prime versions, they introduce new XML attributes and schema versions. Prime 3.1 performs strict schema version checks and uses an older FlowDocument deserializer for text regions — both of which reject files produced by later versions.

The two most common failure modes are:

- **Version mismatch** — Prime 3.1 reads `docProps/app.xml` and refuses to open files with a higher `serializationVersion`.
- **FlowDocument deserializer rejection** — Prime 4+ adds `style=""` and `xml:lang=""` to every `<Run>` element in XAML text regions. The 3.1 deserializer throws a parse error on these attributes.

**mcdx31** addresses both issues without modifying the mathematical content of the worksheet.

---

## Contributing

```bash
git clone https://github.com/PJMEND/mcdx31.git
cd mcdx31
pip install -e ".[dev]"
pytest
```

To regenerate test fixtures:

```bash
python tests/make_fixtures.py
```

---

## License

MIT — see [LICENSE](LICENSE).
