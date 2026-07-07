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
from prompt_builder import PromptBuilder
from pipeline import Pipeline
from validator import Validator

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


def generate_prompt():
    try:
        builder = PromptBuilder()
        result = builder.create_next_prompt()

        console.print("\n[bold green]Prompt generado correctamente.[/bold green]")
        console.print(f"Proyecto: [cyan]{result['project']}[/cyan]")
        console.print(f"Archivo: [cyan]{result['prompt_path']}[/cyan]")
        console.print("\nAbre ese archivo, copia el prompt y pégalo en Gemini.")

    except Exception as error:
        Logger.error(f"Error al generar prompt: {error}")
        console.print(f"\n[red]Error al generar prompt:[/red] {error}")

    pause()


def continue_project():
    try:
        pipeline = Pipeline()
        result = pipeline.continue_project()

        if not result.get("ok"):
            console.print("\n[red]No se puede continuar el proyecto.[/red]")
            for error in result.get("errors", []):
                console.print(f"- {error}")
            pause()
            return

        if result.get("finished"):
            console.print(f"\n[green]{result['message']}[/green]")
            pause()
            return

        if result.get("advanced"):
            console.print("\n[bold green]Proyecto avanzado correctamente.[/bold green]")
            console.print(result["message"])
            console.print(f"Nuevo estado: [cyan]{result['new_state']}[/cyan]")
            pause()
            return

        console.print("\n[bold green]Siguiente prompt generado.[/bold green]")
        console.print(f"Proyecto: [cyan]{result['project']}[/cyan]")
        console.print(f"Etapa: [cyan]{result['state']}[/cyan]")
        console.print(f"IA recomendada: [cyan]{result['ia']}[/cyan]")
        console.print(f"Prompt: [cyan]{result['prompt_path']}[/cyan]")
        console.print(f"Guarda la respuesta en: [cyan]{result['output_file']}[/cyan]")

    except Exception as error:
        Logger.error(f"Error en pipeline: {error}")
        console.print(f"\n[red]Error en pipeline:[/red] {error}")

    pause()


def validate_system():
    validator = Validator()
    errors = validator.validate_system()

    if errors:
        console.print("\n[red]Errores encontrados:[/red]")
        for error in errors:
            console.print(f"- {error}")
    else:
        console.print("\n[bold green]Pruebas automáticas correctas.[/bold green]")

    pause()


def system_status():
    console.print("\n[bold cyan]Estado del Sistema[/bold cyan]\n")
    console.print(f"Versión: {VERSION}")
    console.print("Estado: Desarrollo")
    console.print("Módulo activo: Pipeline + Validator")
    pause()


def main():
    Logger.info("Inicio del sistema")
    ConfigManager()

    while True:
        banner()
        console.print(build_menu())
        console.print("\n5. Generar Prompt de Investigación")
        console.print("6. Continuar Proyecto automáticamente")
        console.print("7. Ejecutar pruebas automáticas")

        option = input("\nSelecciona una opción: ").strip()
        Logger.info(f"Opción seleccionada: {option}")

        if option == "1":
            new_project()
        elif option == "2":
            continue_project()
        elif option == "3":
            console.print("\n[yellow]Configuración estará disponible más adelante.[/yellow]")
            pause()
        elif option == "4":
            system_status()
        elif option == "5":
            generate_prompt()
        elif option == "6":
            continue_project()
        elif option == "7":
            validate_system()
        elif option == "0":
            console.print("\n[green]Hasta pronto.[/green]")
            break
        else:
            console.print("\n[red]Opción inválida.[/red]")
            pause()


if __name__ == "__main__":
    main()