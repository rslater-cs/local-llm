"""A thin, structured wrapper around the Docker Compose CLI."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Sequence

from .config import AppConfig
from .status import StackStatus, StatusReport


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def message(self) -> str:
        return (self.stderr or self.stdout or "Docker Compose command failed").strip()


class ComposeManager:
    def __init__(self, config: AppConfig, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

    def get_status(self) -> StatusReport:
        result = self._run(["ps", "--all", "--format", "json"])
        if not result.ok:
            return StatusReport(StackStatus.ERROR, result.message)
        try:
            containers = self._parse_ps_output(result.stdout)
        except json.JSONDecodeError:
            return StatusReport(StackStatus.ERROR, "Could not read Docker Compose status")
        if not containers:
            return StatusReport(StackStatus.STOPPED)
        states = {str(item.get("State", "")).lower() for item in containers}
        health = {str(item.get("Health", "")).lower() for item in containers}
        if states and states <= {"exited", "stopped"}:
            exit_codes = {int(item.get("ExitCode", 0) or 0) for item in containers}
            if exit_codes <= {0}:
                return StatusReport(StackStatus.STOPPED)
            return StatusReport(StackStatus.UNHEALTHY, "One or more services exited with an error")
        if "unhealthy" in health or states & {"dead", "exited", "stopped", "removing", "restarting"}:
            return StatusReport(StackStatus.UNHEALTHY, ", ".join(sorted(states)))
        if states <= {"running"}:
            if health and health <= {"healthy", ""} and "healthy" in health:
                return StatusReport(StackStatus.READY)
            return StatusReport(StackStatus.RUNNING)
        if states & {"created", "running", "paused"}:
            return StatusReport(StackStatus.STARTING, ", ".join(sorted(states)))
        return StatusReport(StackStatus.STOPPED)

    @staticmethod
    def _parse_ps_output(output: str) -> list[dict[str, object]]:
        """Accept the JSON array and newline-delimited formats used by Compose."""
        if not output.strip():
            return []
        try:
            decoded = json.loads(output)
            if isinstance(decoded, list):
                return decoded
            return [decoded]
        except json.JSONDecodeError as error:
            # Compose v5 emits one JSON object per line rather than one array.
            containers: list[dict[str, object]] = []
            try:
                for line in output.splitlines():
                    if line.strip():
                        item = json.loads(line)
                        if not isinstance(item, dict):
                            raise json.JSONDecodeError("Expected a container object", line, 0)
                        containers.append(item)
            except json.JSONDecodeError:
                raise error
            return containers

    def start(self) -> CommandResult:
        status = self.get_status()
        if status.status == StackStatus.STOPPED:
            listed = self._run(["ps", "--all", "--quiet"])
            # A runtime model selection is Compose configuration. Reconcile it
            # with `up -d` instead of starting a container built for a previous
            # model; otherwise retain the inexpensive normal `start` path.
            if listed.ok and listed.stdout.strip() and not self.config.runtime_env_file.exists():
                return self._run(["start"])
        return self.apply_configuration()

    def stop(self) -> CommandResult:
        return self._run(["stop"])

    def restart(self) -> CommandResult:
        return self._run(["restart"])

    def apply_configuration(self) -> CommandResult:
        return self._run(["up", "-d"], include_runtime_env=True)

    def get_logs(self, tail: int = 200) -> CommandResult:
        return self._run(["logs", "--tail", str(tail)])

    def _run(self, arguments: Sequence[str], include_runtime_env: bool = False) -> CommandResult:
        command = ["docker", "compose", "--project-directory", str(self.config.project_dir), "--file", str(self.config.compose_file)]
        if include_runtime_env:
            # Explicitly include the existing advanced settings before the
            # application-owned model override. Multiple --env-file arguments
            # are applied in order by Docker Compose.
            project_env = self.config.project_dir / ".env"
            if project_env.exists():
                command.extend(["--env-file", str(project_env)])
            if self.config.runtime_env_file.exists():
                command.extend(["--env-file", str(self.config.runtime_env_file)])
        command.extend(arguments)
        try:
            completed = subprocess.run(command, cwd=self.config.project_dir, capture_output=True, text=True, check=False)
            result = CommandResult(tuple(command), completed.returncode, completed.stdout, completed.stderr)
        except FileNotFoundError:
            result = CommandResult(tuple(command), 127, "", "Docker Compose is unavailable. Install Docker Compose and ensure docker is on PATH.")
        except OSError as error:
            result = CommandResult(tuple(command), 1, "", str(error))
        if not result.ok:
            self.logger.error("Compose command failed (%s): %s", result.returncode, " ".join(result.command))
            self.logger.error("stdout: %s", result.stdout.strip())
            self.logger.error("stderr: %s", result.stderr.strip())
        return result
