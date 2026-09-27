"""GGUF model discovery and safe runtime model selection."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig, _read_dotenv


@dataclass(frozen=True)
class Model:
    display_name: str
    absolute_path: Path
    relative_path: Path
    file_size: int


class ModelManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def scan(self) -> list[Model]:
        root = self.config.models_dir.resolve()
        if not root.is_dir():
            return []
        models: list[Model] = []
        for candidate in root.rglob("*.gguf"):
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
                if not resolved.is_file():
                    continue
                relative = resolved.relative_to(root)
                models.append(Model(self._display_name(relative), resolved, relative, resolved.stat().st_size))
            except (OSError, ValueError):
                continue
        return sorted(models, key=lambda model: str(model.relative_path).lower())

    def current_relative_path(self) -> Path | None:
        # Preserve compatibility with the project's original .env configuration
        # until the user makes a selection through the tray application.
        value = _read_dotenv(self.config.runtime_env_file).get("MODEL_FILE")
        if not value:
            value = _read_dotenv(self.config.project_dir / ".env").get("MODEL_FILE")
        return Path(value) if value else None

    def current_model(self) -> Model | None:
        current = self.current_relative_path()
        if current is None:
            return None
        return next((model for model in self.scan() if model.relative_path == current), None)

    def set_active_model(self, model: Model) -> None:
        root = self.config.models_dir.resolve()
        try:
            model.absolute_path.resolve(strict=True).relative_to(root)
        except (OSError, ValueError) as error:
            raise ValueError("Selected model must be located inside models/") from error
        value = model.relative_path.as_posix()
        env_path = self.config.runtime_env_file
        env_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".local-llm.", dir=env_path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("# Runtime state managed by the Local LLM tray application.\n")
                handle.write(f"MODEL_FILE={value}\n")
            os.replace(temporary, env_path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    @staticmethod
    def _display_name(relative_path: Path) -> str:
        parts = relative_path.stem.rsplit("-", 1)
        base = parts[0].replace("_", " ").replace("-", " ")
        return f"{base} — {parts[1]}" if len(parts) == 2 else base
