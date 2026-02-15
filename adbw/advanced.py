import importlib.util
import json
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .adb import adb_cmd, run, run_streaming
from .devices import Device, list_devices

WORKFLOWS_FILE = ".adb_wizard_workflows.json"
PROFILES_FILE = ".adb_wizard_profiles.json"
PLUGINS_DIR = "plugins"


def _read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load_workflows() -> List[Dict[str, Any]]:
    return _read_json(WORKFLOWS_FILE, [])


def save_workflows(workflows: List[Dict[str, Any]]) -> None:
    _write_json(WORKFLOWS_FILE, workflows)


def load_profiles() -> Dict[str, Dict[str, str]]:
    return _read_json(PROFILES_FILE, {})


def save_profiles(profiles: Dict[str, Dict[str, str]]) -> None:
    _write_json(PROFILES_FILE, profiles)


def select_profile(profiles: Dict[str, Dict[str, str]]) -> Optional[str]:
    names = sorted(profiles.keys())
    if not names:
        print("No profiles found.")
        return None
    for i, name in enumerate(names, start=1):
        print(f"{i}) {name}")
    choice = input("Select profile number: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(names)):
        print("Invalid choice.")
        return None
    return names[int(choice) - 1]


def create_or_update_profile() -> None:
    profiles = load_profiles()
    name = input("Profile name: ").strip()
    if not name:
        print("Profile name is required.")
        return
    existing = profiles.get(name, {})
    package_name = input(f"Package name [{existing.get('package_name', '')}]: ").strip() or existing.get("package_name", "")
    activity = input(f"Activity [{existing.get('activity', '')}]: ").strip() or existing.get("activity", "")
    log_tag = input(f"Log tag [{existing.get('log_tag', '*')}]: ").strip() or existing.get("log_tag", "*")
    apk_path = input(f"APK path [{existing.get('apk_path', '')}]: ").strip() or existing.get("apk_path", "")
    profiles[name] = {
        "package_name": package_name,
        "activity": activity,
        "log_tag": log_tag,
        "apk_path": apk_path,
    }
    save_profiles(profiles)
    print(f"Saved profile: {name}")


def delete_profile() -> None:
    profiles = load_profiles()
    name = select_profile(profiles)
    if not name:
        return
    profiles.pop(name, None)
    save_profiles(profiles)
    print(f"Deleted profile: {name}")


def view_profiles() -> None:
    profiles = load_profiles()
    if not profiles:
        print("No profiles found.")
        return
    for name in sorted(profiles):
        p = profiles[name]
        print(f"- {name}: package={p.get('package_name','')}, activity={p.get('activity','')}, log_tag={p.get('log_tag','*')}, apk_path={p.get('apk_path','')}")


def build_workflow() -> None:
    workflows = load_workflows()
    name = input("Workflow name: ").strip()
    if not name:
        print("Workflow name is required.")
        return
    steps: List[Dict[str, str]] = []
    print("Add steps: install_apk | clear_data | launch_app | tail_filtered_logcat")
    while True:
        action = input("Step action (blank to finish): ").strip()
        if not action:
            break
        if action not in ("install_apk", "clear_data", "launch_app", "tail_filtered_logcat"):
            print("Unknown action.")
            continue
        step: Dict[str, str] = {"action": action}
        if action == "install_apk":
            step["apk_path"] = input("apk_path: ").strip()
        if action in ("clear_data", "launch_app"):
            step["package"] = input("package: ").strip()
        if action == "launch_app":
            step["activity"] = input("activity (optional): ").strip()
        if action == "tail_filtered_logcat":
            step["tag"] = input("tag (default *): ").strip() or "*"
            step["priority"] = input("priority [V/D/I/W/E/F/S] (default I): ").strip().upper() or "I"
        steps.append(step)
    if not steps:
        print("No steps added.")
        return
    workflows = [w for w in workflows if w.get("name") != name]
    workflows.append({"name": name, "steps": steps})
    save_workflows(workflows)
    print(f"Saved workflow: {name}")


def list_workflows() -> None:
    workflows = load_workflows()
    if not workflows:
        print("No workflows found.")
        return
    for i, wf in enumerate(workflows, start=1):
        step_names = ", ".join(s.get("action", "?") for s in wf.get("steps", []))
        print(f"{i}) {wf.get('name','unnamed')} [{step_names}]")


def run_workflow(adb_path: str, serial: str) -> None:
    workflows = load_workflows()
    if not workflows:
        print("No workflows found.")
        return
    list_workflows()
    choice = input("Select workflow number: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(workflows)):
        print("Invalid choice.")
        return
    wf = workflows[int(choice) - 1]
    print(f"Running workflow: {wf.get('name','unnamed')}")
    for step in wf.get("steps", []):
        action = step.get("action", "")
        if action == "install_apk":
            apk_path = step.get("apk_path", "")
            if not apk_path:
                print("Skipped install_apk (missing apk_path).")
                continue
            run(adb_cmd(adb_path, serial, "install", "-r", apk_path))
        elif action == "clear_data":
            package = step.get("package", "")
            if package:
                run(adb_cmd(adb_path, serial, "shell", "pm", "clear", package))
        elif action == "launch_app":
            package = step.get("package", "")
            activity = step.get("activity", "")
            if not package:
                print("Skipped launch_app (missing package).")
                continue
            if activity:
                run(adb_cmd(adb_path, serial, "shell", "am", "start", "-n", f"{package}/{activity}"))
            else:
                run(adb_cmd(adb_path, serial, "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"))
        elif action == "tail_filtered_logcat":
            tag = step.get("tag", "*")
            priority = step.get("priority", "I")
            try:
                run_streaming(adb_cmd(adb_path, serial, "logcat", f"{tag}:{priority}", "*:S"))
            except KeyboardInterrupt:
                print()
        else:
            print(f"Unknown step action: {action}")
    print("Workflow complete.")


def run_dev_loop(adb_path: str, serial: str, active_profile: str = "") -> None:
    profiles = load_profiles()
    package = ""
    activity = ""
    tag = "*"
    apk_path = ""
    if active_profile and active_profile in profiles:
        p = profiles[active_profile]
        package = p.get("package_name", "")
        activity = p.get("activity", "")
        tag = p.get("log_tag", "*") or "*"
        apk_path = p.get("apk_path", "")
    elif profiles:
        use_profile = input("Use profile? [y/N]: ").strip().lower() in ("y", "yes")
        if use_profile:
            name = select_profile(profiles)
            if name:
                p = profiles[name]
                package = p.get("package_name", "")
                activity = p.get("activity", "")
                tag = p.get("log_tag", "*") or "*"
                apk_path = p.get("apk_path", "")
    apk_path = input(f"APK path [{apk_path}]: ").strip() or apk_path
    package = input(f"Package [{package}]: ").strip() or package
    activity = input(f"Activity [{activity}]: ").strip() or activity
    tag = input(f"Log tag [{tag}]: ").strip() or tag
    if apk_path:
        run(adb_cmd(adb_path, serial, "install", "-r", apk_path))
    if package:
        run(adb_cmd(adb_path, serial, "shell", "pm", "clear", package), check=False)
        if activity:
            run(adb_cmd(adb_path, serial, "shell", "am", "start", "-n", f"{package}/{activity}"), check=False)
        else:
            run(adb_cmd(adb_path, serial, "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"), check=False)
    print("Starting filtered logcat. Press Ctrl+C to stop.")
    try:
        run_streaming(adb_cmd(adb_path, serial, "logcat", f"{tag}:I", "*:S"))
    except KeyboardInterrupt:
        print()


def export_health_report(adb_path: str, serial: str) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"health_report_{serial}_{timestamp}"
    text_path = f"{base}.txt"
    json_path = f"{base}.json"
    data: Dict[str, Any] = {
        "serial": serial,
        "timestamp": timestamp,
        "getprop_model": run(adb_cmd(adb_path, serial, "shell", "getprop", "ro.product.model"), check=False).stdout.strip(),
        "getprop_brand": run(adb_cmd(adb_path, serial, "shell", "getprop", "ro.product.brand"), check=False).stdout.strip(),
        "android_version": run(adb_cmd(adb_path, serial, "shell", "getprop", "ro.build.version.release"), check=False).stdout.strip(),
        "api_level": run(adb_cmd(adb_path, serial, "shell", "getprop", "ro.build.version.sdk"), check=False).stdout.strip(),
        "storage_df": run(adb_cmd(adb_path, serial, "shell", "df", "-h"), check=False).stdout,
        "battery": run(adb_cmd(adb_path, serial, "shell", "dumpsys", "battery"), check=False).stdout,
        "thermal": run(adb_cmd(adb_path, serial, "shell", "dumpsys", "thermalservice"), check=False).stdout,
        "ip_route": run(adb_cmd(adb_path, serial, "shell", "ip", "route"), check=False).stdout,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    with open(text_path, "w", encoding="utf-8") as f:
        for k, v in data.items():
            f.write(f"## {k}\n{v}\n\n")
    print(f"Wrote reports: {text_path}, {json_path}")


def manage_port_forwarding(adb_path: str, serial: str) -> None:
    while True:
        print("\nPort forwarding")
        print("1) List forwards")
        print("2) Add forward (local->remote)")
        print("3) Remove forward")
        print("4) Add reverse (remote->local)")
        print("5) Remove reverse")
        print("0) Back")
        choice = input("> ").strip()
        if choice == "0":
            return
        if choice == "1":
            out = run([adb_path, "-s", serial, "forward", "--list"], check=False).stdout
            print(out or "(none)")
            continue
        if choice == "2":
            local = input("Local (e.g. tcp:8081): ").strip()
            remote = input("Remote (e.g. tcp:8081): ").strip()
            if local and remote:
                run([adb_path, "-s", serial, "forward", local, remote], check=False)
            continue
        if choice == "3":
            local = input("Local to remove (e.g. tcp:8081): ").strip()
            if local:
                run([adb_path, "-s", serial, "forward", "--remove", local], check=False)
            continue
        if choice == "4":
            remote = input("Remote (e.g. tcp:8081): ").strip()
            local = input("Local (e.g. tcp:8081): ").strip()
            if remote and local:
                run([adb_path, "-s", serial, "reverse", remote, local], check=False)
            continue
        if choice == "5":
            remote = input("Remote to remove (e.g. tcp:8081): ").strip()
            if remote:
                run([adb_path, "-s", serial, "reverse", "--remove", remote], check=False)
            continue
        print("Unknown option.")


def screen_capture_tools(adb_path: str, serial: str) -> None:
    while True:
        print("\nScreen capture tools")
        print("1) Screenshot (PNG)")
        print("2) Screenrecord + pull")
        print("0) Back")
        choice = input("> ").strip()
        if choice == "0":
            return
        if choice == "1":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            local = f"screenshot_{serial}_{timestamp}.png"
            remote = f"/sdcard/{local}"
            run(adb_cmd(adb_path, serial, "shell", "screencap", "-p", remote), check=False)
            run(adb_cmd(adb_path, serial, "pull", remote, local), check=False)
            run(adb_cmd(adb_path, serial, "shell", "rm", remote), check=False)
            print(f"Saved screenshot: {local}")
            continue
        if choice == "2":
            seconds = input("Duration in seconds (max 180, default 15): ").strip() or "15"
            try:
                duration = max(1, min(180, int(seconds)))
            except ValueError:
                duration = 15
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            local = f"screenrecord_{serial}_{timestamp}.mp4"
            remote = f"/sdcard/{local}"
            run(adb_cmd(adb_path, serial, "shell", "screenrecord", "--time-limit", str(duration), remote), check=False)
            run(adb_cmd(adb_path, serial, "pull", remote, local), check=False)
            run(adb_cmd(adb_path, serial, "shell", "rm", remote), check=False)
            print(f"Saved screenrecord: {local}")
            continue
        print("Unknown option.")


def wireless_pairing(adb_path: str) -> None:
    host = input("Pair host (e.g. 192.168.1.10:37099): ").strip()
    code = input("Pair code: ").strip()
    if not host or not code:
        print("Host and pair code are required.")
        return
    run([adb_path, "pair", host, code], check=False)
    connect_host = input("Connect host (e.g. 192.168.1.10:5555): ").strip()
    if connect_host:
        run([adb_path, "connect", connect_host], check=False)


def multi_device_broadcast(adb_path: str) -> None:
    devices = [d for d in list_devices(adb_path) if d.state == "device"]
    if not devices:
        print("No authorized devices available.")
        return
    print("Broadcast action:")
    print("1) Install APK on all devices")
    print("2) Run shell command on all devices")
    choice = input("> ").strip()
    if choice == "1":
        apk = input("APK path: ").strip().strip('"')
        if not apk:
            print("APK path is required.")
            return
        if not os.path.exists(apk):
            print(f"APK path does not exist: {apk}")
            return
        for d in devices:
            print(f"[{d.serial}] installing...")
            run(adb_cmd(adb_path, d.serial, "install", "-r", apk), check=False)
        print("Broadcast install complete.")
        return
    if choice == "2":
        cmd = input("shell> ").strip()
        if not cmd:
            print("Shell command is required.")
            return
        for d in devices:
            print(f"[{d.serial}] running...")
            out = run(adb_cmd(adb_path, d.serial, "shell", cmd), check=False)
            print(f"--- {d.serial} ---")
            if out.stdout:
                print(out.stdout.strip())
            if out.stderr:
                print(out.stderr.strip())
        return
    print("Unknown option.")


def _load_plugin(path: str):
    module_name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_plugins(adb_path: str, serial: str) -> None:
    if not os.path.isdir(PLUGINS_DIR):
        print(f"No plugins directory found: {PLUGINS_DIR}")
        return
    plugin_files = sorted(
        p for p in os.listdir(PLUGINS_DIR) if p.endswith(".py") and not p.startswith("_")
    )
    if not plugin_files:
        print("No plugins found.")
        return

    actions: List[Dict[str, Any]] = []
    for filename in plugin_files:
        path = os.path.join(PLUGINS_DIR, filename)
        try:
            module = _load_plugin(path)
        except Exception as e:
            print(f"Failed loading plugin {filename}: {e}")
            continue
        if module is None:
            continue
        register: Optional[Callable[[], List[Dict[str, Any]]]] = getattr(module, "register", None)
        if not callable(register):
            continue
        try:
            for action in register() or []:
                if callable(action.get("run")) and action.get("name"):
                    actions.append(action)
        except Exception as e:
            print(f"Failed registering actions in plugin {filename}: {e}")

    if not actions:
        print("No valid plugin actions found.")
        return

    print("Plugin actions:")
    for i, action in enumerate(actions, start=1):
        print(f"{i}) {action['name']}")
    choice = input("> ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(actions)):
        print("Invalid choice.")
        return
    selected = actions[int(choice) - 1]
    try:
        selected["run"](adb_path=adb_path, serial=serial, run=run, adb_cmd=adb_cmd)
    except Exception as e:
        print(f"Plugin action failed: {e}")


def apk_insight(adb_path: str, serial: str, signature_check_mode: str = "conservative") -> None:
    apk = input("APK path: ").strip().strip('"')
    if not apk:
        print("APK path is required.")
        return
    if not os.path.exists(apk):
        print(f"APK path does not exist: {apk}")
        return
    # Prefer aapt if available for metadata extraction.
    try:
        out = run(["aapt", "dump", "badging", apk], check=False).stdout
    except Exception:
        out = ""
    package_name = ""
    version_code = ""
    version_name = ""
    min_sdk = ""
    target_sdk = ""
    if out:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                # package: name='com.example' versionCode='1' versionName='1.0'
                parts = line.replace("'", "").split()
                for p in parts:
                    if p.startswith("name="):
                        package_name = p.split("=", 1)[1]
                    if p.startswith("versionCode="):
                        version_code = p.split("=", 1)[1]
                    if p.startswith("versionName="):
                        version_name = p.split("=", 1)[1]
            if line.startswith("sdkVersion:"):
                min_sdk = line.split(":", 1)[1].replace("'", "").strip()
            if line.startswith("targetSdkVersion:"):
                target_sdk = line.split(":", 1)[1].replace("'", "").strip()
    else:
        print("aapt not found or metadata unavailable. Install Android build-tools for richer APK insight.")
    print(f"APK: {apk}")
    print(f"Package: {package_name or 'unknown'}")
    print(f"Version code: {version_code or 'unknown'}")
    print(f"Version name: {version_name or 'unknown'}")
    print(f"minSdk: {min_sdk or 'unknown'}")
    print(f"targetSdk: {target_sdk or 'unknown'}")

    if package_name and version_code.isdigit():
        details = run(adb_cmd(adb_path, serial, "shell", "dumpsys", "package", package_name), check=False).stdout
        installed_code = ""
        has_signing_details = False
        for line in details.splitlines():
            line = line.strip()
            if line.startswith("versionCode="):
                installed_code = line.split("=", 1)[1].split()[0].strip()
            if "signatures:" in line.lower() or "signing" in line.lower():
                has_signing_details = True
        if installed_code.isdigit():
            if int(version_code) < int(installed_code):
                print("Warning: APK versionCode is lower than installed version (potential downgrade).")
        mode = (signature_check_mode or "conservative").lower()
        if mode == "strict" and has_signing_details:
            print("Warning: Strict mode enabled; signature mismatch cannot be verified reliably from dumpsys output.")
        elif mode == "conservative" and has_signing_details:
            # Conservative mode only warns when explicit mismatch wording appears.
            text = details.lower()
            mismatch_signals = ("signature mismatch", "inconsistent certificates", "does not match")
            if any(s in text for s in mismatch_signals):
                print("Warning: Installed package signature may differ; install may fail.")
