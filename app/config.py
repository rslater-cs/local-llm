"""Project paths and application-owned runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class AppConfig:
    project_dir: Path

    @classmethod
    def discover(cls) -> "AppConfig":
        configured = os.environ.get("LOCAL_LLM_PROJECT_DIR")
        project_dir = Path(configured).expanduser() if configured else Path(__file__).resolve().parents[1]
        return cls(project_dir.resolve())

    @property
    def compose_file(self) -> Path:
        return self.project_dir / "compose.yaml"

    @property
    def models_dir(self) -> Path:
        return self.project_dir / "models"

    @property
    def runtime_env_file(self) -> Path:
        return self.project_dir / ".local-llm.env"

    @property
    def app_log_file(self) -> Path:
        return self.project_dir / "local-llm-tray.log"

    @property
    def webui_url(self) -> str:
        port = _read_dotenv(self.project_dir / ".env").get("OPENWEBUI_PORT", "3000")
        return f"http://localhost:{port}"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.compose_file.is_file():
            errors.append(f"Missing {self.compose_file.name} in {self.project_dir}")
        if not self.models_dir.is_dir():
            errors.append(f"Missing models directory: {self.models_dir}")
        parsed = urlparse(self.webui_url)
        if not parsed.scheme or not parsed.netloc:
            errors.append("Invalid Open WebUI URL")
        return errors
