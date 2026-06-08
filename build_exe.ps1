# Build mcdx31.exe — single-file Windows executable
# Run from repo root:  .\build_exe.ps1

$ErrorActionPreference = "Stop"

Write-Host "Installing PyInstaller..." -ForegroundColor Cyan
py -m pip install --quiet pyinstaller

Write-Host "Building exe..." -ForegroundColor Cyan
py -m PyInstaller `
    --onefile `
    --windowed `
    --name mcdx31 `
    --paths src `
    launcher.py

if (Test-Path "dist\mcdx31.exe") {
    $size = [math]::Round((Get-Item "dist\mcdx31.exe").Length / 1MB, 1)
    Write-Host "Done: dist\mcdx31.exe  ($size MB)" -ForegroundColor Green
} else {
    Write-Host "Build failed — check output above." -ForegroundColor Red
    exit 1
}
