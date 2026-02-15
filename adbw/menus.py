import os
from typing import List

from .actions import (
    collect_bugreport_bundle,
    connect_over_wifi,
    disconnect_wifi,
    install_split_apks,
    launch_app,
    list_packages,
    save_logcat_snapshot,
    show_package_info,
    tail_filtered_logcat,
)
from .advanced import (
    app_permission_manager,
    apk_insight,
    build_workflow,
    create_or_update_profile,
    delete_profile,
    intent_deeplink_runner,
    interactive_package_search,
    export_health_report,
    list_workflows,
    manage_port_forwarding,
    manage_device_aliases,
    multi_device_broadcast,
    network_diagnostics_pack,
    prerequisite_health_check,
    process_service_inspector,
    restore_device_state,
    run_dev_loop,
    run_plugins,
    run_workflow,
    scheduled_log_capture,
    screen_capture_tools,
    select_profile,
    snapshot_device_state,
    view_profiles,
    wireless_pairing,
    load_profiles,
)
from .adb import adb_cmd, ensure_adb, run, run_streaming
from .config import SETTINGS_FILE, Settings, save_settings
from .devices import Device, list_devices, pick_device, show_device_summary
from .ui_strings import (
    ADB_MENU_LINES,
    ADVANCED_MENU_LINES,
    APP_PACKAGE_MENU_LINES,
    DEVICE_SESSION_MENU_LINES,
    FILE_TRANSFER_MENU_LINES,
    LOGGING_MENU_LINES,
    PLATFORM_TOOLS_MENU_LINES,
    UTILITIES_MENU_LINES,
)


def confirm(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in ("y", "yes")


def _print_menu(lines: List[str]) -> None:
    for line in lines:
        print(line)


def _non_empty_input(prompt: str) -> str:
    return input(prompt).strip().strip('"')


def _handle_shell_command(adb_path: str, serial: str, shell_history: List[str]) -> None:
    cmd = input("shell> ").strip()
    if cmd == "!history":
        if not shell_history:
            print("No shell command history.")
        else:
            for i, item in enumerate(shell_history, start=1):
                print(f"{i}) {item}")
        return
    if cmd.startswith("!"):
        idx = cmd[1:]
        if idx.isdigit() and 1 <= int(idx) <= len(shell_history):
            cmd = shell_history[int(idx) - 1]
            print(f"shell> {cmd}")
        else:
            print("Invalid history index.")
            return
    if not cmd:
        print("Shell command is required.")
        return
    shell_history.append(cmd)
    proc = run(adb_cmd(adb_path, serial, "shell", cmd), check=False)
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)


def _handle_install_apk(adb_path: str, serial: str) -> None:
    apk = _non_empty_input("Path to APK: ")
    if not apk:
        print("APK path is required.")
        return
    if not os.path.exists(apk):
        print(f"APK path does not exist: {apk}")
        return
    run(adb_cmd(adb_path, serial, "install", "-r", apk))
    print("Installed.")


def _handle_push(adb_path: str, serial: str) -> None:
    src = _non_empty_input("Local source path: ")
    if not src:
        print("Source path is required.")
        return
    if not os.path.exists(src):
        print(f"Local source path does not exist: {src}")
        return
    dst = _non_empty_input("Device destination path: ")
    if not dst:
        print("Destination path is required.")
        return
    run(adb_cmd(adb_path, serial, "push", src, dst))
    print("Push complete.")


def _handle_pull(adb_path: str, serial: str) -> None:
    src = _non_empty_input("Device source path: ")
    if not src:
        print("Source path is required.")
        return
    dst = _non_empty_input("Local destination path (default: current directory): ") or "."
    run(adb_cmd(adb_path, serial, "pull", src, dst))
    print("Pull complete.")


def _handle_package_action(adb_path: str, serial: str, prompt: str, command: List[str], success: str) -> None:
    package = input(prompt).strip()
    if not package:
        print("Package name is required.")
        return
    if not confirm(command[0].format(package=package)):
        return
    run(adb_cmd(adb_path, serial, *command[1:], package))
    print(success)


def _handle_reboot_menu(adb_path: str, serial: str) -> None:
    print("1) Reboot system")
    print("2) Reboot recovery")
    print("3) Reboot bootloader")
    reboot_choice = input("> ").strip()
    if reboot_choice == "1":
        if confirm("Reboot device to system now?"):
            run(adb_cmd(adb_path, serial, "reboot"))
    elif reboot_choice == "2":
        if confirm("Reboot device to recovery now?"):
            run(adb_cmd(adb_path, serial, "reboot", "recovery"))
    elif reboot_choice == "3":
        if confirm("Reboot device to bootloader now?"):
            run(adb_cmd(adb_path, serial, "reboot", "bootloader"))
    else:
        print("Unknown option.")


def _show_device_session_menu(adb_path: str, device: Device, settings: Settings) -> Device:
    while True:
        print("\nDevice and session")
        print(f"Device: {device.serial} [{device.state}]")
        _print_menu(DEVICE_SESSION_MENU_LINES)
        choice = input("> ").strip()

        if choice == "0":
            return device
        if choice == "1":
            show_device_summary(adb_path, device.serial)
            continue
        if choice == "2":
            devices = list_devices(adb_path)
            new_device = pick_device(devices)
            if new_device.state == "unauthorized":
                print("Selected device is unauthorized. Unlock and accept USB debugging, then retry.")
                continue
            device = new_device
            if settings.remember_last_device:
                settings.last_device_serial = device.serial
                save_settings(settings)
            print(f"Switched to {device.serial}.")
            continue
        if choice == "3":
            _handle_reboot_menu(adb_path, device.serial)
            continue
        if choice == "4":
            if not confirm("Connect this device over Wi-Fi now?"):
                continue
            connect_over_wifi(adb_path, device.serial)
            continue
        if choice == "5":
            if not confirm("Disconnect Wi-Fi adb endpoint(s) now?"):
                continue
            disconnect_wifi(adb_path)
            continue
        print("Unknown option.")


def _show_app_package_menu(adb_path: str, device: Device, settings: Settings) -> None:
    while True:
        print("\nApp and package")
        print(f"Device: {device.serial} [{device.state}]")
        _print_menu(APP_PACKAGE_MENU_LINES)
        choice = input("> ").strip()

        if choice == "0":
            return
        if choice == "1":
            _handle_install_apk(adb_path, device.serial)
            continue
        if choice == "2":
            install_split_apks(adb_path, device.serial)
            continue
        if choice == "3":
            apk_insight(adb_path, device.serial, signature_check_mode=settings.apk_signature_check_mode)
            continue
        if choice == "4":
            list_packages(adb_path, device.serial)
            continue
        if choice == "5":
            show_package_info(adb_path, device.serial)
            continue
        if choice == "6":
            launch_app(adb_path, device.serial)
            continue
        if choice == "7":
            _handle_package_action(
                adb_path,
                device.serial,
                "Package name to uninstall: ",
                ["Uninstall {package}?", "uninstall"],
                "Uninstall command sent.",
            )
            continue
        if choice == "8":
            _handle_package_action(
                adb_path,
                device.serial,
                "Package name to force-stop: ",
                ["Force-stop {package}?", "shell", "am", "force-stop"],
                "Force-stop command sent.",
            )
            continue
        if choice == "9":
            _handle_package_action(
                adb_path,
                device.serial,
                "Package name to clear app data: ",
                ["Clear app data for {package}?", "shell", "pm", "clear"],
                "Clear data command sent.",
            )
            continue
        print("Unknown option.")


def _show_file_transfer_menu(adb_path: str, device: Device) -> None:
    while True:
        print("\nFile transfer")
        print(f"Device: {device.serial} [{device.state}]")
        _print_menu(FILE_TRANSFER_MENU_LINES)
        choice = input("> ").strip()

        if choice == "0":
            return
        if choice == "1":
            _handle_push(adb_path, device.serial)
            continue
        if choice == "2":
            _handle_pull(adb_path, device.serial)
            continue
        print("Unknown option.")


def _show_logging_menu(adb_path: str, device: Device) -> None:
    while True:
        print("\nLogging and diagnostics")
        print(f"Device: {device.serial} [{device.state}]")
        _print_menu(LOGGING_MENU_LINES)
        choice = input("> ").strip()

        if choice == "0":
            return
        if choice == "1":
            try:
                run_streaming(adb_cmd(adb_path, device.serial, "logcat"))
            except KeyboardInterrupt:
                print()
            continue
        if choice == "2":
            save_logcat_snapshot(adb_path, device.serial)
            continue
        if choice == "3":
            tail_filtered_logcat(adb_path, device.serial)
            continue
        if choice == "4":
            if not confirm("Collect diagnostics bundle now? This may take a while."):
                continue
            collect_bugreport_bundle(adb_path, device.serial)
            continue
        if choice == "5":
            export_health_report(adb_path, device.serial)
            continue
        print("Unknown option.")


def _show_workflow_manager(adb_path: str, serial: str) -> None:
    while True:
        print("\nWorkflow manager")
        print("1) List workflows")
        print("2) Create/update workflow")
        print("3) Run workflow")
        print("0) Back")
        choice = input("> ").strip()
        if choice == "0":
            return
        if choice == "1":
            list_workflows()
            continue
        if choice == "2":
            build_workflow()
            continue
        if choice == "3":
            run_workflow(adb_path, serial)
            continue
        print("Unknown option.")


def _show_profile_manager(settings: Settings) -> None:
    while True:
        print("\nProfile manager")
        print(f"Active profile: {settings.active_profile or 'none'}")
        print("1) List profiles")
        print("2) Create/update profile")
        print("3) Delete profile")
        print("4) Set active profile")
        print("0) Back")
        choice = input("> ").strip()
        if choice == "0":
            return
        if choice == "1":
            view_profiles()
            continue
        if choice == "2":
            create_or_update_profile()
            continue
        if choice == "3":
            delete_profile()
            if settings.active_profile and settings.active_profile not in load_profiles():
                settings.active_profile = ""
                save_settings(settings)
            continue
        if choice == "4":
            name = select_profile(load_profiles())
            if name:
                settings.active_profile = name
                save_settings(settings)
                print(f"Active profile set: {name}")
            continue
        print("Unknown option.")


def _show_utilities_menu(adb_path: str, device: Device, shell_history: List[str], settings: Settings) -> None:
    while True:
        print("\nUtilities")
        print(f"Device: {device.serial} [{device.state}]")
        _print_menu(UTILITIES_MENU_LINES)
        choice = input("> ").strip()

        if choice == "0":
            return
        if choice == "1":
            _handle_shell_command(adb_path, device.serial, shell_history)
            continue
        if choice == "2":
            _show_workflow_manager(adb_path, device.serial)
            continue
        if choice == "3":
            _show_profile_manager(settings)
            continue
        if choice == "4":
            run_dev_loop(adb_path, device.serial, active_profile=settings.active_profile)
            continue
        if choice == "5":
            run_plugins(adb_path, device.serial)
            continue
        if choice == "6":
            multi_device_broadcast(adb_path)
            continue
        if choice == "7":
            interactive_package_search(adb_path, device.serial)
            continue
        if choice == "8":
            scheduled_log_capture(adb_path, device.serial)
            continue
        print("Unknown option.")


def _show_advanced_menu(adb_path: str, device: Device) -> None:
    while True:
        print("\nAdvanced")
        print(f"Device: {device.serial} [{device.state}]")
        _print_menu(ADVANCED_MENU_LINES)
        choice = input("> ").strip()

        if choice == "0":
            return
        if choice == "1":
            manage_port_forwarding(adb_path, device.serial)
            continue
        if choice == "2":
            screen_capture_tools(adb_path, device.serial)
            continue
        if choice == "3":
            wireless_pairing(adb_path)
            continue
        if choice == "4":
            print("1) Create snapshot")
            print("2) Restore snapshot")
            action = input("> ").strip()
            if action == "1":
                snapshot_device_state(adb_path, device.serial)
            elif action == "2":
                restore_device_state(adb_path, device.serial)
            else:
                print("Unknown option.")
            continue
        if choice == "5":
            app_permission_manager(adb_path, device.serial)
            continue
        if choice == "6":
            intent_deeplink_runner(adb_path, device.serial)
            continue
        if choice == "7":
            process_service_inspector(adb_path, device.serial)
            continue
        if choice == "8":
            network_diagnostics_pack(adb_path, device.serial)
            continue
        if choice == "9":
            manage_device_aliases(adb_path)
            continue
        if choice == "10":
            prerequisite_health_check(adb_path)
            continue
        print("Unknown option.")


def show_basic_menu(adb_path: str, device: Device, settings: Settings) -> Device:
    shell_history: List[str] = []

    while True:
        print("\nADB Wizard")
        print(f"Device: {device.serial} [{device.state}]")
        _print_menu(ADB_MENU_LINES)
        choice = input("> ").strip()

        if choice == "0":
            return device
        if choice == "1":
            device = _show_device_session_menu(adb_path, device, settings)
            continue
        if choice == "2":
            _show_app_package_menu(adb_path, device, settings)
            continue
        if choice == "3":
            _show_file_transfer_menu(adb_path, device)
            continue
        if choice == "4":
            _show_logging_menu(adb_path, device)
            continue
        if choice == "5":
            _show_utilities_menu(adb_path, device, shell_history, settings)
            continue
        if choice == "6":
            _show_advanced_menu(adb_path, device)
            continue
        print("Unknown option.")


def show_platform_tools_menu(prefer_project_local: bool) -> bool:
    while True:
        print("\nPlatform tools")
        _print_menu(PLATFORM_TOOLS_MENU_LINES)
        choice = input("> ").strip()

        if choice == "0":
            return False
        if choice == "1":
            ensure_adb(force_install=True, prefer_project_local=prefer_project_local)
            print("Project-local platform-tools installation complete (./platform-tools, not system-wide).")
            return True
        print("Unknown option.")


def show_settings_menu(settings: Settings) -> bool:
    while True:
        print("\nSettings")
        local_pref = "ON" if settings.prefer_project_local_platform_tools else "OFF"
        remember = "ON" if settings.remember_last_device else "OFF"
        dry_run = "ON" if settings.dry_run else "OFF"
        debug_log = "ON" if settings.debug_logging else "OFF"
        redact = "ON" if settings.redact_exports else "OFF"
        transcript = "ON" if settings.action_transcript_enabled else "OFF"
        signature_mode = settings.apk_signature_check_mode
        print(f"1) Prefer project-local platform-tools (currently: {local_pref})")
        print(f"2) Remember last selected device (currently: {remember})")
        print(f"3) Dry run mode (currently: {dry_run})")
        print(f"4) Debug logging to file (currently: {debug_log})")
        print(f"5) APK signature check mode (currently: {signature_mode})")
        print(f"6) Redact exports/transcripts (currently: {redact})")
        print(f"7) Action transcript logging (currently: {transcript})")
        print(f"8) ADB retry count (currently: {settings.adb_retry_count})")
        print(f"9) Command timeout seconds (currently: {settings.command_timeout_sec})")
        print(f"10) Clear remembered device (currently: {settings.last_device_serial or 'none'})")
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
        if choice == "2":
            settings.remember_last_device = not settings.remember_last_device
            if not settings.remember_last_device:
                settings.last_device_serial = ""
            save_settings(settings)
            current = "ON" if settings.remember_last_device else "OFF"
            print(f"Saved {SETTINGS_FILE}: remember_last_device={current}")
            return True
        if choice == "3":
            settings.dry_run = not settings.dry_run
            save_settings(settings)
            current = "ON" if settings.dry_run else "OFF"
            print(f"Saved {SETTINGS_FILE}: dry_run={current}")
            return True
        if choice == "4":
            settings.debug_logging = not settings.debug_logging
            save_settings(settings)
            current = "ON" if settings.debug_logging else "OFF"
            print(f"Saved {SETTINGS_FILE}: debug_logging={current}")
            return True
        if choice == "5":
            modes = ["off", "conservative", "strict"]
            current = settings.apk_signature_check_mode if settings.apk_signature_check_mode in modes else "conservative"
            next_mode = modes[(modes.index(current) + 1) % len(modes)]
            settings.apk_signature_check_mode = next_mode
            save_settings(settings)
            print(f"Saved {SETTINGS_FILE}: apk_signature_check_mode={next_mode}")
            return True
        if choice == "6":
            settings.redact_exports = not settings.redact_exports
            save_settings(settings)
            state = "ON" if settings.redact_exports else "OFF"
            print(f"Saved {SETTINGS_FILE}: redact_exports={state}")
            return True
        if choice == "7":
            settings.action_transcript_enabled = not settings.action_transcript_enabled
            save_settings(settings)
            state = "ON" if settings.action_transcript_enabled else "OFF"
            print(f"Saved {SETTINGS_FILE}: action_transcript_enabled={state}")
            return True
        if choice == "8":
            val = input("ADB retry count (1-10): ").strip()
            if val.isdigit() and 1 <= int(val) <= 10:
                settings.adb_retry_count = int(val)
                save_settings(settings)
                print(f"Saved {SETTINGS_FILE}: adb_retry_count={settings.adb_retry_count}")
                return True
            print("Invalid retry count.")
            continue
        if choice == "9":
            val = input("Command timeout seconds (5-3600): ").strip()
            if val.isdigit() and 5 <= int(val) <= 3600:
                settings.command_timeout_sec = int(val)
                save_settings(settings)
                print(f"Saved {SETTINGS_FILE}: command_timeout_sec={settings.command_timeout_sec}")
                return True
            print("Invalid timeout value.")
            continue
        if choice == "10":
            settings.last_device_serial = ""
            save_settings(settings)
            print(f"Saved {SETTINGS_FILE}: last_device_serial cleared.")
            return True
        print("Unknown option.")
