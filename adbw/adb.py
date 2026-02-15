import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from typing import List, Optional

from .config import LOCAL_PLATFORM_TOOLS_DIR, Settings
from .errors import AdbWizardError

RUNTIME_DRY_RUN = False
RUNTIME_DEBUG_LOGGING = False
RUNTIME_DEBUG_LOG_FILE = "adb_cli_py_debug.log"
RUNTIME_REDACT_EXPORTS = True
RUNTIME_ACTION_TRANSCRIPT_ENABLED = False
RUNTIME_ACTION_TRANSCRIPT_FILE = "adb_cli_py_transcript.log"
RUNTIME_ADB_RETRY_COUNT = 3
RUNTIME_COMMAND_TIMEOUT_SEC = 120


def set_runtime_options(settings: Settings) -> None:
    global RUNTIME_DRY_RUN
    global RUNTIME_DEBUG_LOGGING
    global RUNTIME_DEBUG_LOG_FILE
    global RUNTIME_REDACT_EXPORTS
    global RUNTIME_ACTION_TRANSCRIPT_ENABLED
    global RUNTIME_ACTION_TRANSCRIPT_FILE
    global RUNTIME_ADB_RETRY_COUNT
    global RUNTIME_COMMAND_TIMEOUT_SEC
    RUNTIME_DRY_RUN = settings.dry_run
    RUNTIME_DEBUG_LOGGING = settings.debug_logging
    RUNTIME_DEBUG_LOG_FILE = settings.debug_log_file or "adb_cli_py_debug.log"
    RUNTIME_REDACT_EXPORTS = settings.redact_exports
    RUNTIME_ACTION_TRANSCRIPT_ENABLED = settings.action_transcript_enabled
    RUNTIME_ACTION_TRANSCRIPT_FILE = settings.action_transcript_file or "adb_cli_py_transcript.log"
    RUNTIME_ADB_RETRY_COUNT = max(1, min(10, int(settings.adb_retry_count)))
    RUNTIME_COMMAND_TIMEOUT_SEC = max(5, min(3600, int(settings.command_timeout_sec)))


def redact_sensitive_text(text: str) -> str:
    if not text:
        return text
    out = text
    patterns = [
        (r"\b(?:\d[ -]*?){13,19}\b", "[REDACTED_CARD]"),
        (r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[REDACTED_EMAIL]"),
        (r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)\d{3,4}[-.\s]?\d{3,4}\b", "[REDACTED_PHONE]"),
        (r"\b(?:token|apikey|api_key|secret|password)\s*[:=]\s*\S+\b", "[REDACTED_SECRET]"),
        (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED_IP]"),
    ]
    for pat, repl in patterns:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out


def redact_if_enabled(text: str) -> str:
    return redact_sensitive_text(text) if RUNTIME_REDACT_EXPORTS else text


def append_transcript(entry: str) -> None:
    if not RUNTIME_ACTION_TRANSCRIPT_ENABLED:
        return
    line = f"{datetime.now().isoformat(timespec='seconds')} {entry}\n"
    try:
        with open(RUNTIME_ACTION_TRANSCRIPT_FILE, "a", encoding="utf-8") as f:
            f.write(redact_if_enabled(line))
    except OSError:
        pass


def log_debug(message: str) -> None:
    if not RUNTIME_DEBUG_LOGGING:
        return
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}\n"
    try:
        with open(RUNTIME_DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def is_transient_adb_failure(stdout: str, stderr: str) -> bool:
    text = f"{stdout}\n{stderr}".lower()
    transient_signals = (
        "device offline",
        "device still authorizing",
        "closed",
        "cannot connect",
        "connection reset",
        "protocol fault",
    )
    return any(token in text for token in transient_signals)


def command_failure_suggestion(stdout: str, stderr: str) -> str:
    text = f"{stdout}\n{stderr}".lower()
    if "unauthorized" in text:
        return "Suggestion: unlock the phone and accept the USB debugging prompt."
    if "no devices/emulators found" in text:
        return "Suggestion: connect a device, enable USB debugging, and re-run."
    if "more than one device/emulator" in text:
        return "Suggestion: choose a single target device from the ADB menu."
    if "device offline" in text:
        return "Suggestion: reconnect USB or restart adb server and retry."
    if "failed to stat" in text or "no such file" in text:
        return "Suggestion: verify the source/destination path exists."
    return "Suggestion: run again with debug logging enabled to capture full command output."


def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    command_text = " ".join(cmd)
    is_adb_command = bool(cmd) and ("adb" in os.path.basename(cmd[0]).lower())
    max_attempts = RUNTIME_ADB_RETRY_COUNT if is_adb_command else 1
    last_proc: Optional[subprocess.CompletedProcess] = None

    for attempt in range(1, max_attempts + 1):
        if RUNTIME_DRY_RUN:
            print(f"[DRY RUN] {command_text}")
            log_debug(f"DRY_RUN command={command_text}")
            append_transcript(f"DRY_RUN command={command_text}")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        log_debug(f"RUN attempt={attempt} command={command_text}")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=RUNTIME_COMMAND_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            proc = subprocess.CompletedProcess(cmd, 124, "", f"Command timed out after {RUNTIME_COMMAND_TIMEOUT_SEC}s")
        last_proc = proc
        log_debug(
            f"RESULT attempt={attempt} returncode={proc.returncode} stdout={proc.stdout.strip()} stderr={proc.stderr.strip()}"
        )
        append_transcript(
            f"RUN attempt={attempt} command={command_text} rc={proc.returncode}\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}"
        )

        if proc.returncode == 0:
            return proc

        if not check:
            return proc

        if is_adb_command and attempt < max_attempts and is_transient_adb_failure(proc.stdout, proc.stderr):
            print(f"Transient adb error (attempt {attempt}/{max_attempts}), retrying...")
            time.sleep(1.0)
            continue

        suggestion = command_failure_suggestion(proc.stdout, proc.stderr)
        raise AdbWizardError(
            f"Command failed ({proc.returncode}): {command_text}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}\n{suggestion}"
        )

    if last_proc is None:
        raise AdbWizardError("Command failed before execution.")
    return last_proc


def run_streaming(cmd: List[str]) -> None:
    command_text = " ".join(cmd)
    if RUNTIME_DRY_RUN:
        print(f"[DRY RUN] {command_text}")
        log_debug(f"DRY_RUN streaming command={command_text}")
        append_transcript(f"DRY_RUN streaming command={command_text}")
        return
    log_debug(f"RUN streaming command={command_text}")
    append_transcript(f"RUN streaming command={command_text}")
    try:
        subprocess.run(cmd, timeout=RUNTIME_COMMAND_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        print(f"Streaming command timed out after {RUNTIME_COMMAND_TIMEOUT_SEC}s")
        append_transcript(f"TIMEOUT streaming command={command_text}")


def local_adb_path() -> str:
    local = os.path.join(os.getcwd(), LOCAL_PLATFORM_TOOLS_DIR, "adb")
    if platform.system() == "Windows":
        local += ".exe"
    return local


def find_adb(prefer_project_local: bool = False) -> Optional[str]:
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
    tmp_dir = tempfile.mkdtemp(prefix="adb_cli_py_")
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


def adb_source_label(adb_path: str) -> str:
    if os.path.abspath(adb_path) == os.path.abspath(local_adb_path()):
        return f"project-local (./{LOCAL_PLATFORM_TOOLS_DIR})"
    return "global PATH"
