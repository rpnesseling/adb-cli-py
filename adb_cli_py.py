import argparse
import json
import sys

from adbw.app import main
from adbw.api import run_json_command
from adbw.errors import AdbWizardError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="adb-cli-py")
    parser.add_argument("--json", action="store_true", help="Run in non-interactive JSON/API mode.")
    parser.add_argument("--cmd", help="Command id for JSON/API mode.")
    parser.add_argument("--serial", help="Target device serial for JSON/API mode.")
    parser.add_argument(
        "--params",
        help="Command params as JSON object string or comma-separated key=value pairs.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        if args.json:
            if not args.cmd:
                raise AdbWizardError("--cmd is required when --json is used.")
            payload = run_json_command(cmd=args.cmd, serial=args.serial, params_raw=args.params)
            print(json.dumps(payload, indent=2))
            sys.exit(0)
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
    except AdbWizardError as e:
        if args.json:
            print(json.dumps({"ok": False, "error": str(e)}, indent=2))
            sys.exit(1)
        print(f"\nError: {e}")
