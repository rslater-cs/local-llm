import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.compose import ComposeManager
from app.config import AppConfig
from app.status import StackStatus


class ComposeManagerTests(unittest.TestCase):
    def test_status_reports_stopped_when_compose_has_no_containers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = type("Completed", (), {"returncode": 0, "stdout": "[]", "stderr": ""})()
            with patch("app.compose.subprocess.run", return_value=completed):
                self.assertEqual(ComposeManager(AppConfig(Path(directory))).get_status().status, StackStatus.STOPPED)

    def test_status_reports_ready_when_all_health_checks_are_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = json.dumps([{"State": "running", "Health": "healthy"}, {"State": "running", "Health": "healthy"}])
            completed = type("Completed", (), {"returncode": 0, "stdout": payload, "stderr": ""})()
            with patch("app.compose.subprocess.run", return_value=completed):
                self.assertEqual(ComposeManager(AppConfig(Path(directory))).get_status().status, StackStatus.READY)

    def test_status_accepts_compose_v5_newline_delimited_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = "\n".join([
                json.dumps({"Service": "llama", "State": "running", "Health": ""}),
                json.dumps({"Service": "open-webui", "State": "running", "Health": "healthy"}),
            ])
            completed = type("Completed", (), {"returncode": 0, "stdout": payload, "stderr": ""})()
            with patch("app.compose.subprocess.run", return_value=completed):
                self.assertEqual(ComposeManager(AppConfig(Path(directory))).get_status().status, StackStatus.READY)

    def test_cleanly_exited_services_are_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = "\n".join([
                json.dumps({"Service": "llama", "State": "exited", "ExitCode": 0, "Health": ""}),
                json.dumps({"Service": "open-webui", "State": "exited", "ExitCode": 0, "Health": ""}),
            ])
            completed = type("Completed", (), {"returncode": 0, "stdout": payload, "stderr": ""})()
            with patch("app.compose.subprocess.run", return_value=completed):
                self.assertEqual(ComposeManager(AppConfig(Path(directory))).get_status().status, StackStatus.STOPPED)

    def test_failed_exit_is_unhealthy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = json.dumps([{"Service": "llama", "State": "exited", "ExitCode": 1, "Health": ""}])
            completed = type("Completed", (), {"returncode": 0, "stdout": payload, "stderr": ""})()
            with patch("app.compose.subprocess.run", return_value=completed):
                self.assertEqual(ComposeManager(AppConfig(Path(directory))).get_status().status, StackStatus.UNHEALTHY)
