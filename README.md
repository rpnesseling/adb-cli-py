# adb-wizard

Simple interactive Python CLI for common Android Debug Bridge (ADB) tasks.

## Features

- Detects connected Android devices with `adb devices -l`
- Lets you choose a device when multiple are connected
- Shows basic device properties (brand, model, Android version)
- Installs APKs with `adb install -r`
- Transfers files with guided `adb push` and `adb pull` prompts
- Runs arbitrary `adb shell` commands
- Tails `logcat` output
- Auto-installs project-local Android platform-tools in `./platform-tools` when `adb` is not found
- Prints which `adb` binary is active (project-local or global `PATH`)

## Requirements

- Python 3.9+
- Either:
  - `adb` already available on your `PATH`, or
  - internet access on first run so the tool can download project-local platform-tools to `./platform-tools`
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

Settings file:

`adb_wizard.py` reads `.adb_wizard_settings.json` from the project root and updates it from the Settings menu.
If the file does not exist, it is created when a setting is toggled.

```json
{
  "prefer_project_local_platform_tools": false
}
```

Settings:
- `prefer_project_local_platform_tools`: Prefer `./platform-tools/adb` over global `adb` on `PATH` when both exist.

On startup, the tool prints which `adb` is being used (path + source label: project-local or global `PATH`).

## Menu Options

Top-level menu:
1. ADB menu
2. Platform tools
3. Settings
0. Exit

Platform tools:
1. Force install project-local platform-tools (`./platform-tools`, not system-wide)
0. Back

Settings:
1. Toggle `prefer_project_local_platform_tools`
0. Back

ADB menu:
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
5. Push file to device  
   Prompts for local source path and device destination path, then runs `adb push`
6. Pull file from device  
   Prompts for device source path and local destination path, then runs `adb pull`
0. Exit

## Example Session

```text
ADB Wizard
Device: R58M123456A [device]
1) Show device props
2) Install APK
3) Run shell command
4) Tail logcat (Ctrl+C to stop)
5) Push file to device
6) Pull file from device
0) Exit
> 1
```

## Troubleshooting

- `adb not found`
  - Install Android platform-tools system-wide, or place `adb` in `./platform-tools/` for project-local use (not system-wide)
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
