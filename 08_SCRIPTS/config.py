"""
=========================================================
CIPS
Configuración Global
=========================================================
"""

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = ROOT / "01_CONFIG"


class ConfigManager:
    """
    Carga archivos YAML de configuración.
    """

    def __init__(self):
        self.global_config = self.load_yaml("config_global.yaml")
        self.pipeline = self.load_yaml("pipeline.yaml")
        self.llm = self.load_yaml("llm.yaml")

    def load_yaml(self, filename: str) -> dict:

        file = CONFIG_DIR / filename

        if not file.exists():
            return {}

        with open(file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get(self, section: str, default=None):

        return self.global_config.get(section, default)