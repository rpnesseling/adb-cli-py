#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Installing build dependencies..."
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install pyinstaller

echo "Running tests..."
"$PYTHON_BIN" -m unittest discover -s tests -p "test_*.py"

echo "Building adb-wizard binary..."
"$PYTHON_BIN" -m PyInstaller --clean --noconfirm --onefile --name adb-wizard adb_wizard.py

echo "Done. Output: dist/adb-wizard"

