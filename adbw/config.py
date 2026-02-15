import json
import os
from dataclasses import dataclass

from .errors import AdbWizardError

SETTINGS_FILE = ".adb_wizard_settings.json"
LOCAL_PLATFORM_TOOLS_DIR = "platform-tools"


@dataclass
class Settings:
    prefer_project_local_platform_tools: bool = False
    remember_last_device: bool = True
    last_device_serial: str = ""
    active_profile: str = ""
    apk_signature_check_mode: str = "conservative"
    dry_run: bool = False
    debug_logging: bool = False
    debug_log_file: str = "adb_wizard_debug.log"


def load_settings() -> Settings:
    if not os.path.exists(SETTINGS_FILE):
        return Settings()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        mode = str(raw.get("apk_signature_check_mode", "conservative")).lower()
        if mode not in ("off", "conservative", "strict"):
            mode = "conservative"
        return Settings(
            prefer_project_local_platform_tools=bool(raw.get("prefer_project_local_platform_tools", False)),
            remember_last_device=bool(raw.get("remember_last_device", True)),
            last_device_serial=str(raw.get("last_device_serial", "")),
            active_profile=str(raw.get("active_profile", "")),
            apk_signature_check_mode=mode,
            dry_run=bool(raw.get("dry_run", False)),
            debug_logging=bool(raw.get("debug_logging", False)),
            debug_log_file=str(raw.get("debug_log_file", "adb_wizard_debug.log")),
        )
    except (OSError, json.JSONDecodeError):
        return Settings()


def save_settings(settings: Settings) -> None:
    payload = {
        "prefer_project_local_platform_tools": settings.prefer_project_local_platform_tools,
        "remember_last_device": settings.remember_last_device,
        "last_device_serial": settings.last_device_serial,
        "active_profile": settings.active_profile,
        "apk_signature_check_mode": settings.apk_signature_check_mode,
        "dry_run": settings.dry_run,
        "debug_logging": settings.debug_logging,
        "debug_log_file": settings.debug_log_file,
    }
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
    except OSError as e:
        raise AdbWizardError(f"Failed to write settings file ({SETTINGS_FILE}): {e}") from e
