"""
CIPS
Content Intelligence Production System
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
from project_manager import ProjectManager

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
            title="Consejo IA",
        )
    )


def pause():
    input("\nPresiona ENTER para continuar...")


def new_project():
    console.print("\n[bold green]Nuevo Proyecto[/bold green]\n")

    tema = input("Escribe el tema del contenido:\n\n> ").strip()

    if not tema:
        console.print("\n[red]El tema no puede estar vacío.[/red]")
        pause()
        return

    try:
        manager = ProjectManager()
        project = manager.create_project(tema)

        Logger.info(f"Proyecto creado: {project['id']}")

        console.print("\n[bold green]Proyecto creado correctamente.[/bold green]")
        console.print(f"ID: [cyan]{project['id']}[/cyan]")
        console.print(f"Tema: [cyan]{project['tema']}[/cyan]")
        console.print(f"Ruta: [cyan]{project['path']}[/cyan]")

    except Exception as error:
        Logger.error(f"Error al crear proyecto: {error}")
        console.print(f"\n[red]Error al crear proyecto:[/red] {error}")

    pause()


def system_status():
    console.print("\n[bold cyan]Estado del Sistema[/bold cyan]\n")
    console.print(f"Versión: {VERSION}")
    console.print("Estado: Desarrollo")
    console.print("Módulo activo: Project Manager")
    pause()


def main():
    Logger.info("Inicio del sistema")
    ConfigManager()

    while True:
        banner()
        console.print(build_menu())

        option = input("\nSelecciona una opción: ").strip()
        Logger.info(f"Opción seleccionada: {option}")

        if option == "1":
            new_project()
        elif option == "2":
            console.print("\n[yellow]Continuar Proyecto estará disponible en el siguiente módulo.[/yellow]")
            pause()
        elif option == "3":
            console.print("\n[yellow]Configuración estará disponible más adelante.[/yellow]")
            pause()
        elif option == "4":
            system_status()
        elif option == "0":
            console.print("\n[green]Hasta pronto.[/green]")
            break
        else:
            console.print("\n[red]Opción inválida.[/red]")
            pause()


if __name__ == "__main__":
    main()