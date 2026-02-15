import os
import platform
import shutil
import subprocess
import tempfile
import json
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Device:
    serial: str
    state: str
    description: str = ""


@dataclass
class Settings:
    prefer_project_local_platform_tools: bool = False


class AdbWizardError(Exception):
    pass


SETTINGS_FILE = ".adb_wizard_settings.json"
LOCAL_PLATFORM_TOOLS_DIR = "platform-tools"


def load_settings() -> Settings:
    if not os.path.exists(SETTINGS_FILE):
        return Settings()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return Settings(
            prefer_project_local_platform_tools=bool(raw.get("prefer_project_local_platform_tools", False)),
        )
    except (OSError, json.JSONDecodeError):
        return Settings()


def save_settings(settings: Settings) -> None:
    payload = {
        "prefer_project_local_platform_tools": settings.prefer_project_local_platform_tools,
    }
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
    except OSError as e:
        raise AdbWizardError(f"Failed to write settings file ({SETTINGS_FILE}): {e}") from e


def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AdbWizardError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def local_adb_path() -> str:
    local = os.path.join(os.getcwd(), LOCAL_PLATFORM_TOOLS_DIR, "adb")
    if platform.system() == "Windows":
        local += ".exe"
    return local


def find_adb(prefer_project_local: bool = False) -> Optional[str]:
    # Fallback to script-managed project-local platform-tools in ./platform-tools (not system-wide).
    local = local_adb_path()
    adb = shutil.which("adb")

    if prefer_project_local and os.path.exists(local):
        return local
    if adb:
        return adb
    if os.path.exists(local):
        return local

    return None


def platform_tools_url() -> str:
    system = platform.system()
    if system == "Windows":
        return "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    if system == "Linux":
        return "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"
    if system == "Darwin":
        return "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip"
    raise AdbWizardError(f"Unsupported OS for platform-tools auto-install: {system}")


def install_platform_tools() -> None:
    url = platform_tools_url()
    tmp_dir = tempfile.mkdtemp(prefix="adb_wizard_")
    archive_path = os.path.join(tmp_dir, f"{LOCAL_PLATFORM_TOOLS_DIR}.zip")
    local_install_path = os.path.join(os.getcwd(), LOCAL_PLATFORM_TOOLS_DIR)

    try:
        print(f"Downloading Android platform-tools for project-local use (not system-wide) from: {url}")
        urllib.request.urlretrieve(url, archive_path)
        print(f"Extracting into project-local path: {local_install_path} (not system-wide)")
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(os.getcwd())
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        raise AdbWizardError(f"Failed to download platform-tools: {e}") from e
    except zipfile.BadZipFile as e:
        raise AdbWizardError("Downloaded platform-tools archive is invalid.") from e
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def ensure_adb(force_install: bool = False, prefer_project_local: bool = False) -> str:
    if force_install:
        print("Forcing project-local platform-tools install in ./platform-tools (not system-wide)...")
        install_platform_tools()

    adb_path = find_adb(prefer_project_local=prefer_project_local)
    if adb_path:
        return adb_path

    print("adb not found. Attempting project-local platform-tools install in ./platform-tools (not system-wide)...")
    install_platform_tools()

    adb_path = find_adb(prefer_project_local=prefer_project_local)
    if adb_path:
        return adb_path

    raise AdbWizardError(
        "adb was still not found after project-local platform-tools install (not system-wide).\n"
        f"Check installation in ./{LOCAL_PLATFORM_TOOLS_DIR} and try again."
    )


def adb_cmd(adb_path: str, serial: Optional[str], *args: str) -> List[str]:
    cmd = [adb_path]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return cmd


def list_devices(adb_path: str) -> List[Device]:
    run([adb_path, "start-server"], check=False)
    out = run([adb_path, "devices", "-l"]).stdout.strip().splitlines()

    devices: List[Device] = []
    for line in out[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"
        desc = " ".join(parts[2:]) if len(parts) > 2 else ""
        devices.append(Device(serial=serial, state=state, description=desc))
    return devices


def pick_device(devices: List[Device]) -> Device:
    if not devices:
        raise AdbWizardError("No devices found. Plug in device, enable USB debugging, and try again.")
    if len(devices) == 1:
        return devices[0]

    print("Multiple devices detected:")
    for i, d in enumerate(devices, start=1):
        print(f"{i}) {d.serial} [{d.state}] {d.description}")

    while True:
        choice = input("Select device number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(devices):
            return devices[int(choice) - 1]
        print("Invalid choice.")


def show_basic_menu(adb_path: str, device: Device) -> None:
    serial = device.serial
    while True:
        print("\nADB Wizard")
        print(f"Device: {serial} [{device.state}]")
        print("1) Show device props")
        print("2) Install APK")
        print("3) Run shell command")
        print("4) Tail logcat (Ctrl+C to stop)")
        print("5) Push file to device")
        print("6) Pull file from device")
        print("0) Exit")
        choice = input("> ").strip()

        if choice == "0":
            return
        elif choice == "1":
            model = run(adb_cmd(adb_path, serial, "shell", "getprop", "ro.product.model")).stdout.strip()
            brand = run(adb_cmd(adb_path, serial, "shell", "getprop", "ro.product.brand")).stdout.strip()
            ver = run(adb_cmd(adb_path, serial, "shell", "getprop", "ro.build.version.release")).stdout.strip()
            print(f"Brand: {brand}\nModel: {model}\nAndroid: {ver}")
        elif choice == "2":
            apk = input("Path to APK: ").strip().strip('"')
            run(adb_cmd(adb_path, serial, "install", "-r", apk))
            print("Installed.")
        elif choice == "3":
            cmd = input("shell> ").strip()
            proc = run(adb_cmd(adb_path, serial, "shell", cmd), check=False)
            print(proc.stdout)
            if proc.stderr:
                print(proc.stderr)
        elif choice == "4":
            try:
                subprocess.run(adb_cmd(adb_path, serial, "logcat"))
            except KeyboardInterrupt:
                pass
        elif choice == "5":
            src = input("Local source path: ").strip().strip('"')
            if not src:
                print("Source path is required.")
                continue
            if not os.path.exists(src):
                print(f"Local source path does not exist: {src}")
                continue
            dst = input("Device destination path: ").strip().strip('"')
            if not dst:
                print("Destination path is required.")
                continue
            run(adb_cmd(adb_path, serial, "push", src, dst))
            print("Push complete.")
        elif choice == "6":
            src = input("Device source path: ").strip().strip('"')
            if not src:
                print("Source path is required.")
                continue
            dst = input("Local destination path (default: current directory): ").strip().strip('"')
            if not dst:
                dst = "."
            run(adb_cmd(adb_path, serial, "pull", src, dst))
            print("Pull complete.")
        else:
            print("Unknown option.")


def show_platform_tools_menu() -> bool:
    while True:
        print("\nPlatform tools")
        print("1) Force install project-local platform-tools (./platform-tools, not system-wide)")
        print("0) Back")
        choice = input("> ").strip()

        if choice == "0":
            return False
        if choice == "1":
            ensure_adb(force_install=True)
            print("Project-local platform-tools installation complete (./platform-tools, not system-wide).")
            return True
        print("Unknown option.")


def show_settings_menu(settings: Settings) -> bool:
    while True:
        print("\nSettings")
        current = "ON" if settings.prefer_project_local_platform_tools else "OFF"
        print(f"1) Prefer project-local platform-tools (currently: {current})")
        print("0) Back")
        choice = input("> ").strip()

        if choice == "0":
            return False
        if choice == "1":
            settings.prefer_project_local_platform_tools = not settings.prefer_project_local_platform_tools
            save_settings(settings)
            current = "ON" if settings.prefer_project_local_platform_tools else "OFF"
            print(f"Saved {SETTINGS_FILE}: prefer_project_local_platform_tools={current}")
            return True
        print("Unknown option.")


def adb_source_label(adb_path: str) -> str:
    if os.path.abspath(adb_path) == os.path.abspath(local_adb_path()):
        return f"project-local (./{LOCAL_PLATFORM_TOOLS_DIR})"
    return "global PATH"


def main():
    settings = load_settings()
    prefer_project_local = settings.prefer_project_local_platform_tools

    adb_path = ensure_adb(
        force_install=False,
        prefer_project_local=prefer_project_local,
    )
    print(f"Using adb: {adb_path} [{adb_source_label(adb_path)}]")
    cached_device: Optional[Device] = None

    while True:
        print("\nMain")
        print("1) ADB menu")
        print("2) Platform tools")
        print("3) Settings")
        print("0) Exit")
        choice = input("> ").strip()

        if choice == "0":
            return
        if choice == "1":
            devices = list_devices(adb_path)
            device = pick_device(devices)
            if device.state == "unauthorized":
                raise AdbWizardError(
                    "Device is unauthorized. Unlock phone and accept the USB debugging prompt, then try again."
                )
            cached_device = device
            show_basic_menu(adb_path, cached_device)
            continue
        if choice == "2":
            if show_platform_tools_menu():
                adb_path = ensure_adb(force_install=False, prefer_project_local=prefer_project_local)
                print(f"Using adb: {adb_path} [{adb_source_label(adb_path)}]")
            continue
        if choice == "3":
            if show_settings_menu(settings):
                prefer_project_local = settings.prefer_project_local_platform_tools
                adb_path = ensure_adb(force_install=False, prefer_project_local=prefer_project_local)
                print(f"Using adb: {adb_path} [{adb_source_label(adb_path)}]")
            continue
        print("Unknown option.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
    except AdbWizardError as e:
        print(f"\nError: {e}")
