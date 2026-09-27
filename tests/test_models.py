from pathlib import Path
import tempfile
import unittest

from app.config import AppConfig
from app.models import Model, ModelManager


class ModelManagerTests(unittest.TestCase):
    def test_scans_nested_gguf_files_and_writes_only_relative_model_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            models = root / "models" / "nested"
            models.mkdir(parents=True)
            model_file = models / "Qwen3-8B-Q4_K_M.gguf"
            model_file.write_bytes(b"model")
            config = AppConfig(root)
            manager = ModelManager(config)

            discovered = manager.scan()

            self.assertEqual(len(discovered), 1)
            self.assertEqual(discovered[0].relative_path, Path("nested/Qwen3-8B-Q4_K_M.gguf"))
            self.assertEqual(discovered[0].display_name, "Qwen3 8B — Q4_K_M")
            manager.set_active_model(discovered[0])
            self.assertEqual(config.runtime_env_file.read_text(), "# Runtime state managed by the Local LLM tray application.\nMODEL_FILE=nested/Qwen3-8B-Q4_K_M.gguf\n")

    def test_rejects_model_outside_models_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "models").mkdir()
            outside = root / "outside.gguf"
            outside.write_bytes(b"model")
            manager = ModelManager(AppConfig(root))
            invalid = Model("outside", outside, Path("outside.gguf"), outside.stat().st_size)
            with self.assertRaises(ValueError):
                manager.set_active_model(invalid)
