# adb-wizard

Simple interactive Python CLI for common Android Debug Bridge (ADB) tasks.

## Features

- Detects connected Android devices with `adb devices -l`
- Lets you choose a device when multiple are connected
- Shows basic device properties (brand, model, Android version)
- Installs APKs with `adb install -r`
- Runs arbitrary `adb shell` commands
- Tails `logcat` output

## Requirements

- Python 3.9+
- ADB available in one of these locations:
  - On your `PATH`
  - `./platform-tools/adb` (`adb.exe` on Windows)
- Android device with:
  - Developer Options enabled
  - USB Debugging enabled
  - USB debugging authorization accepted on-device

## Quick Start

```powershell
python adb_wizard.py
```

If one device is connected, it is selected automatically.  
If multiple devices are connected, choose one from the prompt.

## Menu Options

1. Show device props  
   Prints:
   - `ro.product.brand`
   - `ro.product.model`
   - `ro.build.version.release`
2. Install APK  
   Prompts for a local APK path and installs with replace (`-r`)
3. Run shell command  
   Prompts for a shell command and prints stdout/stderr
4. Tail logcat  
   Streams logs until `Ctrl+C`
0. Exit

## Example Session

```text
ADB Wizard
Device: R58M123456A [device]
1) Show device props
2) Install APK
3) Run shell command
4) Tail logcat (Ctrl+C to stop)
0) Exit
> 1
```

## Troubleshooting

- `adb not found`
  - Install Android platform-tools, or place `adb` in `./platform-tools/`
- `No devices found`
  - Check cable/USB mode, enable USB debugging, run `adb devices`
- `Device is unauthorized`
  - Unlock the phone and accept the USB debugging prompt
- `Interrupted. Exiting.`
  - Printed when `Ctrl+C` is used to exit the app

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes and test locally
4. Open a pull request with a clear description

For bug reports, include:
- OS version
- Python version
- `adb version` output
- Steps to reproduce

## License

This project is licensed under the MIT License. See `LICENSE` for details.
