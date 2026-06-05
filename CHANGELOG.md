# Changelog

All notable changes to this project will be documented here.

## [0.1.0] — 2026-06-06

### Added
- Core conversion engine: downgrades Mathcad Prime 4–12 `.mcdx` files to Prime 3.1 format
- CLI (`mcdx-downgrade`): single-file and batch folder conversion, in-place mode, dry-run, backup, verbose, validation flags
- GUI (`mcdx-downgrade-gui`): Tkinter window with file picker, options, scrollable log
- Post-conversion validation: ZIP integrity, version check, XAML attribute check, result.xml check
- Python API: `downgrade()` and `validate_mcdx()` for programmatic use
- 48 unit and integration tests, all passing without Mathcad installed
- Zero external runtime dependencies (Python standard library only)
