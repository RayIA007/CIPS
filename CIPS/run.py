"""
=========================================================
CIPS
Content Intelligence Production System
=========================================================
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.append(str(ROOT / "08_SCRIPTS"))

from rich.console import Console
from rich.panel import Panel

from menu import build_menu
from logger import Logger
from config import ConfigManager

console = Console()

VERSION = "0.1.0"


def banner():

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

            title="Consejo IA"

        )

    )


def main():

    Logger.info("Inicio del sistema")

    ConfigManager()

    banner()

    console.print(build_menu())

    opcion = input("\nSelecciona una opción: ")

    Logger.info(f"Opción seleccionada: {opcion}")

    console.print()

    console.print(f"Opción elegida: {opcion}")

    console.print()

    console.print("[green]Build 002B correcto.[/green]")


if __name__ == "__main__":

    main()