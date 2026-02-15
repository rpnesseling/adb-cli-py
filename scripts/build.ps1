param(
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing build dependencies..."
& $Python -m pip install --upgrade pip
& $Python -m pip install pyinstaller

Write-Host "Running tests..."
& $Python -m unittest discover -s tests -p "test_*.py"

Write-Host "Building adb-wizard binary..."
& $Python -m PyInstaller --clean --noconfirm --onefile --name adb-wizard adb_wizard.py

Write-Host "Done. Output: dist/adb-wizard.exe"

