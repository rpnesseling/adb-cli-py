import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .adb import adb_cmd, adb_source_label, ensure_adb, run, set_runtime_options
from .config import load_settings
from .devices import get_device_summary_data, list_devices
from .errors import AdbWizardError


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def parse_params(raw: Optional[str]) -> Dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except json.JSONDecodeError:
        pass
    params: Dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k.strip()] = v.strip()
    return params


def _ensure_target_serial(adb_path: str, serial: Optional[str]) -> str:
    if serial:
        return serial
    devices = [d for d in list_devices(adb_path) if d.state == "device"]
    if len(devices) == 1:
        return devices[0].serial
    if not devices:
        raise AdbWizardError("No authorized connected devices found. Pass --serial to target explicitly.")
    raise AdbWizardError("Multiple devices connected. Pass --serial to target a specific device.")


def _devices_list(adb_path: str) -> Dict[str, Any]:
    devices = list_devices(adb_path)
    return {
        "devices": [
            {"serial": d.serial, "state": d.state, "description": d.description}
            for d in devices
        ]
    }


def _device_summary(adb_path: str, serial: str) -> Dict[str, Any]:
    return {"summary": get_device_summary_data(adb_path, serial)}


def _shell_run(adb_path: str, serial: str, params: Dict[str, str]) -> Dict[str, Any]:
    cmd = params.get("command", "")
    if not cmd:
        raise AdbWizardError("Missing parameter: command")
    proc = run(adb_cmd(adb_path, serial, "shell", cmd), check=False)
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def _package_list(adb_path: str, serial: str, params: Dict[str, str]) -> Dict[str, Any]:
    third_party = _parse_bool(params.get("third_party", "false"))
    args: List[str] = ["pm", "list", "packages"]
    if third_party:
        args.append("-3")
    out = run(adb_cmd(adb_path, serial, "shell", *args)).stdout
    packages = [ln.replace("package:", "").strip() for ln in out.splitlines() if ln.strip()]
    return {"packages": packages, "third_party": third_party}


def _package_info(adb_path: str, serial: str, params: Dict[str, str]) -> Dict[str, Any]:
    package = params.get("package", "")
    if not package:
        raise AdbWizardError("Missing parameter: package")
    paths = run(adb_cmd(adb_path, serial, "shell", "pm", "path", package), check=False).stdout.strip().splitlines()
    details = run(adb_cmd(adb_path, serial, "shell", "dumpsys", "package", package), check=False).stdout
    version_name = ""
    version_code = ""
    for line in details.splitlines():
        line = line.strip()
        if not version_name and line.startswith("versionName="):
            version_name = line.split("=", 1)[1].strip()
        if not version_code and line.startswith("versionCode="):
            version_code = line.split("=", 1)[1].strip().split()[0]
        if version_name and version_code:
            break
    return {
        "package": package,
        "version_name": version_name or "unknown",
        "version_code": version_code or "unknown",
        "paths": paths,
    }


def _apk_install(adb_path: str, serial: str, params: Dict[str, str]) -> Dict[str, Any]:
    apk_path = params.get("apk_path", "")
    if not apk_path:
        raise AdbWizardError("Missing parameter: apk_path")
    if not os.path.exists(apk_path):
        raise AdbWizardError(f"APK path does not exist: {apk_path}")
    proc = run(adb_cmd(adb_path, serial, "install", "-r", apk_path), check=False)
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def _file_push(adb_path: str, serial: str, params: Dict[str, str]) -> Dict[str, Any]:
    src = params.get("src", "")
    dst = params.get("dst", "")
    if not src or not dst:
        raise AdbWizardError("Missing parameters: src,dst")
    if not os.path.exists(src):
        raise AdbWizardError(f"Local source path does not exist: {src}")
    proc = run(adb_cmd(adb_path, serial, "push", src, dst), check=False)
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def _file_pull(adb_path: str, serial: str, params: Dict[str, str]) -> Dict[str, Any]:
    src = params.get("src", "")
    dst = params.get("dst", ".")
    if not src:
        raise AdbWizardError("Missing parameter: src")
    proc = run(adb_cmd(adb_path, serial, "pull", src, dst), check=False)
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def _logcat_snapshot(adb_path: str, serial: str, params: Dict[str, str]) -> Dict[str, Any]:
    output = params.get("output", "")
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"logcat_{serial}_{timestamp}.txt"
    out = run(adb_cmd(adb_path, serial, "logcat", "-d"), check=False).stdout
    with open(output, "w", encoding="utf-8") as f:
        f.write(out)
    return {"output": output}


def run_json_command(cmd: str, serial: Optional[str], params_raw: Optional[str]) -> Dict[str, Any]:
    settings = load_settings()
    set_runtime_options(settings)
    adb_path = ensure_adb(force_install=False, prefer_project_local=settings.prefer_project_local_platform_tools)
    params = parse_params(params_raw)

    result: Dict[str, Any] = {
        "ok": True,
        "cmd": cmd,
        "adb_path": adb_path,
        "adb_source": adb_source_label(adb_path),
    }

    if cmd == "system.info":
        result["data"] = {
            "settings_file_present": os.path.exists(".adb_cli_py_settings.json"),
            "cwd": os.getcwd(),
            "adb_path": adb_path,
            "adb_source": adb_source_label(adb_path),
        }
        return result

    if cmd == "devices.list":
        result["data"] = _devices_list(adb_path)
        return result

    target_serial = _ensure_target_serial(adb_path, serial)
    result["serial"] = target_serial

    handlers = {
        "device.summary": lambda: _device_summary(adb_path, target_serial),
        "shell.run": lambda: _shell_run(adb_path, target_serial, params),
        "package.list": lambda: _package_list(adb_path, target_serial, params),
        "package.info": lambda: _package_info(adb_path, target_serial, params),
        "apk.install": lambda: _apk_install(adb_path, target_serial, params),
        "file.push": lambda: _file_push(adb_path, target_serial, params),
        "file.pull": lambda: _file_pull(adb_path, target_serial, params),
        "logcat.snapshot": lambda: _logcat_snapshot(adb_path, target_serial, params),
    }
    handler = handlers.get(cmd)
    if handler is None:
        raise AdbWizardError(
            "Unknown --cmd. Supported: system.info, devices.list, device.summary, shell.run, "
            "package.list, package.info, apk.install, file.push, file.pull, logcat.snapshot"
        )
    result["data"] = handler()
    return result

