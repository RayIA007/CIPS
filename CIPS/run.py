"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 015
Archivo  : run.py
Estado   : RELEASE
=========================================================

Punto de entrada principal de CIPS.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "08_SCRIPTS"))

from rich.console import Console
from rich.panel import Panel

from config import ConfigManager
from logger import Logger
from menu import build_menu
from menu_controller import MenuController
from runtime_constants import RUNTIME_VERSION


console = Console()
VERSION = f"{RUNTIME_VERSION}.0"


def banner() -> None:
    console.print()
    console.print(
        Panel.fit(
            f"""
[bold cyan]
CIPS
Content Intelligence Production System

Versión {VERSION}
[/bold cyan]
""",
            title="Consejo IA",
        )
    )


def main() -> None:
    Logger.info("Inicio del sistema")
    ConfigManager()

    controller = MenuController()
    running = True

    while running:
        banner()
        console.print(build_menu())

        option = input(
            "\nSelecciona una opción: "
        ).strip()

        Logger.info(
            f"Opción seleccionada: {option}"
        )

        running = controller.dispatch(option)


if __name__ == "__main__":
    main()