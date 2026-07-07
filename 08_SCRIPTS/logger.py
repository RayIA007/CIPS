"""
=========================================================
CIPS
Sistema de Logs
=========================================================
"""

from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

LOG_DIR = ROOT / "07_LOGS"

LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "cips.log"


class Logger:

    @staticmethod
    def info(message: str):

        Logger.write("INFO", message)

    @staticmethod
    def warning(message: str):

        Logger.write("WARNING", message)

    @staticmethod
    def error(message: str):

        Logger.write("ERROR", message)

    @staticmethod
    def write(level: str, message: str):

        with open(LOG_FILE, "a", encoding="utf-8") as file:

            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            file.write(f"[{fecha}] {level}: {message}\n")