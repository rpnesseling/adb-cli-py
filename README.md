# adb-wizard

A practical interactive CLI for everyday Android Debug Bridge (ADB) work.

`adb-wizard` helps you connect to devices, run common ADB actions quickly, and automate repeated tasks with workflows, profiles, and plugins.

## What It Does

### Device and session
- Detect connected devices and choose target device
- Remember last selected device (optional)
- Show a one-screen device summary
- Reboot to system, recovery, or bootloader
- Connect/disconnect over Wi-Fi ADB

### App and package
- Install APK (`install -r`)
- Install split APK sets (`install-multiple -r`)
- APK insight (package/version/minSdk/targetSdk when `aapt` is available)
- List packages, inspect package details, launch app
- Uninstall, force-stop, and clear app data

### File transfer
- Push local file/path to device
- Pull from device to local path

### Logging and diagnostics
- Live `logcat`
- Filtered `logcat`
- Save `logcat` snapshot
- Collect diagnostics bundle (`logcat` + `bugreport`)
- Export health report (`.json` + `.txt`)

### Automation and power tools
- Workflow manager (create/list/run step-based workflows)
- Profile manager (store app/dev defaults)
- App dev loop mode (install + clear + launch + filtered logcat)
- Multi-device broadcast (install APK or run shell on all connected devices)
- Plugin actions from `plugins/*.py`
- Interactive package search with quick actions

### Advanced utilities
- Port forward/reverse manager
- Screen capture tools (screenshot/screenrecord)
- Wireless pairing (`adb pair`)
- Device snapshot/restore helpers
- Permission manager (grant/revoke/list)
- Intent/deep-link runner
- Process/service inspector
- Network diagnostics pack export
- Device alias manager
- Prerequisite health check

## Requirements

- Python 3.9+
- Android device with USB debugging enabled (and authorization accepted on-device)
- `adb` available either:
  - globally on `PATH`, or
  - as project-local `./platform-tools/adb` (auto-installed if needed)

## Install and Run

```powershell
python adb_wizard.py
```

If `adb` is missing, the tool downloads Android platform-tools into `./platform-tools` for project-local use (not system-wide install).

## Main Menus

### Root menu
1. `ADB menu`
2. `Platform tools`
3. `Settings`
0. `Exit`

### ADB menu groups
1. `Device and session`
2. `App and package`
3. `File transfer`
4. `Logging and diagnostics`
5. `Utilities`
6. `Advanced`
0. `Exit`

## Settings

Runtime settings are stored in:
- `.adb_wizard_settings.json`

If the file does not exist, it is created when settings are saved.

Example template:
- `.adb_wizard_settings.example.json`

Important options:
- `prefer_project_local_platform_tools`: prefer `./platform-tools/adb` over global `adb`
- `remember_last_device`
- `apk_signature_check_mode`: `off` / `conservative` / `strict`
- `dry_run`
- `debug_logging`
- `redact_exports`
- `action_transcript_enabled`
- `adb_retry_count`
- `command_timeout_sec`

## Local Data Files

These are user-local runtime files and are ignored by git:
- `.adb_wizard_settings.json`
- `.adb_wizard_profiles.json`
- `.adb_wizard_workflows.json`
- `.adb_wizard_aliases.json`

Example templates in repo:
- `.adb_wizard_settings.example.json`
- `.adb_wizard_profiles.example.json`
- `.adb_wizard_workflows.example.json`
- `.adb_wizard_aliases.example.json`

## JSON/API Mode (Non-Interactive)

Use `--json` with `--cmd` for scripting/CI.

```powershell
python adb_wizard.py --json --cmd devices.list
```

Optional:
- `--serial <device-serial>`
- `--params <json-or-kv>`

Supported commands:
- `system.info`
- `devices.list`
- `device.summary`
- `shell.run`
- `package.list`
- `package.info`
- `apk.install`
- `file.push`
- `file.pull`
- `logcat.snapshot`

Examples:

```powershell
python adb_wizard.py --json --cmd device.summary --serial ABC123
python adb_wizard.py --json --cmd shell.run --serial ABC123 --params "command=getprop ro.build.version.release"
python adb_wizard.py --json --cmd file.push --serial ABC123 --params "src=C:/tmp/a.txt,dst=/sdcard/a.txt"
```

## Workflows and Profiles

### Workflows
- File: `.adb_wizard_workflows.json`
- Example: `.adb_wizard_workflows.example.json`
- Supported step actions:
  - `install_apk`
  - `clear_data`
  - `launch_app`
  - `tail_filtered_logcat`

### Profiles
- File: `.adb_wizard_profiles.json`
- Example: `.adb_wizard_profiles.example.json`
- Fields:
  - `package_name`
  - `activity`
  - `log_tag`
  - `apk_path`

## Plugins

- Folder: `plugins/`
- Example: `plugins/example_plugin.py`

Plugin contract:
- Export a `register()` function
- Return a list of action dictionaries
- Each action should have:
  - `name`: label shown in menu
  - `run`: callable receiving `adb_path`, `serial`, `run`, `adb_cmd`

Plugin load/registration/action errors are reported and do not terminate the app.

## Build Binaries

### Local build

Windows:

```powershell
.\scripts\build.ps1
```

Linux/macOS:

```bash
./scripts/build.sh
```

Output:
- Windows: `dist/adb-wizard.exe`
- Linux/macOS: `dist/adb-wizard`

### GitHub Actions

Workflow file: `.github/workflows/build.yml`

- Push to `main` and pull requests run build + tests
- Tag pushes matching `v*` also create a GitHub Release

## Release Assets

GitHub Releases include:
- `adb-wizard-windows.exe`
- `adb-wizard-linux`
- `adb-wizard-macos`
- `SHA256SUMS.txt`

## Project Layout

- `adb_wizard.py`: CLI entrypoint
- `adbw/app.py`: app startup and root flow
- `adbw/menus.py`: interactive menus
- `adbw/adb.py`: command execution, retries, adb discovery/install
- `adbw/devices.py`: device discovery/selection/summary
- `adbw/actions.py`: core ADB actions
- `adbw/advanced.py`: workflows/profiles/plugins and advanced tools
- `adbw/api.py`: JSON/API mode
- `adbw/config.py`: settings model and persistence

## Testing

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Troubleshooting

- `No devices found`
  - Check USB cable/mode, enable USB debugging, authorize host
- `Device is unauthorized`
  - Unlock device and accept USB debugging prompt
- `adb not found`
  - Let adb-wizard auto-install project-local `platform-tools`, or install adb globally
- Command errors
  - Enable debug logging in Settings and inspect `adb_wizard_debug.log`

## License

MIT. See `LICENSE`.
