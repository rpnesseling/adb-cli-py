import os
import tempfile
import unittest

from adbw import config
from adbw.adb import command_failure_suggestion, is_transient_adb_failure
from adbw.config import Settings, load_settings, save_settings


class TestAdbHelpers(unittest.TestCase):
    def test_transient_failure_detection(self) -> None:
        self.assertTrue(is_transient_adb_failure("", "error: device offline"))
        self.assertTrue(is_transient_adb_failure("connection reset by peer", ""))
        self.assertFalse(is_transient_adb_failure("", "unauthorized"))

    def test_failure_suggestions(self) -> None:
        self.assertIn("unlock the phone", command_failure_suggestion("", "unauthorized"))
        self.assertIn("connect a device", command_failure_suggestion("", "no devices/emulators found"))
        self.assertIn("verify the source/destination path", command_failure_suggestion("", "failed to stat"))


class TestSettingsRoundTrip(unittest.TestCase):
    def test_save_and_load_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_settings_file = config.SETTINGS_FILE
            try:
                config.SETTINGS_FILE = os.path.join(tmpdir, ".adb_wizard_settings.json")
                expected = Settings(
                    prefer_project_local_platform_tools=True,
                    remember_last_device=False,
                    last_device_serial="ABC123",
                    apk_signature_check_mode="strict",
                    dry_run=True,
                    debug_logging=True,
                    debug_log_file="custom.log",
                )
                save_settings(expected)
                actual = load_settings()
            finally:
                config.SETTINGS_FILE = old_settings_file

        self.assertEqual(actual, expected)

    def test_invalid_signature_mode_falls_back_to_conservative(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_settings_file = config.SETTINGS_FILE
            try:
                config.SETTINGS_FILE = os.path.join(tmpdir, ".adb_wizard_settings.json")
                with open(config.SETTINGS_FILE, "w", encoding="utf-8") as f:
                    f.write(
                        """{
  "apk_signature_check_mode": "not-a-valid-mode"
}
"""
                    )
                actual = load_settings()
            finally:
                config.SETTINGS_FILE = old_settings_file

        self.assertEqual(actual.apk_signature_check_mode, "conservative")


if __name__ == "__main__":
    unittest.main()
