"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 015
Archivo  : menu_controller.py
Estado   : RELEASE
=========================================================

Controlador principal del menú de CIPS.
"""

from rich.console import Console

from logger import Logger
from project_manager import ProjectManager
from pipeline_engine import PipelineEngine
from validator_engine import Validator
from knowledge_module_builder import KnowledgeModuleBuilder


class MenuController:
    """
    Centraliza todas las acciones disponibles desde el menú principal.
    """

    def __init__(self):

        self.console = Console()

        self.project_manager = ProjectManager()
        self.pipeline_engine = PipelineEngine()
        self.validator = Validator()
        self.knowledge_builder = KnowledgeModuleBuilder()

    # --------------------------------------------------
    # Utilidades
    # --------------------------------------------------

    def pause(self):
        input("\nPresiona ENTER para continuar...")

    # --------------------------------------------------
    # PROYECTOS
    # --------------------------------------------------

    def new_project(self):

        self.console.print(
            "\n[bold green]Nuevo Proyecto[/bold green]\n"
        )

        tema = input(
            "Escribe el tema del contenido:\n\n> "
        ).strip()

        if not tema:
            self.console.print(
                "\n[red]El tema no puede estar vacío.[/red]"
            )
            self.pause()
            return

        try:

            project = self.project_manager.create_project(
                tema
            )

            Logger.info(
                f"Proyecto creado: {project['id']}"
            )

            self.console.print(
                "\n[bold green]Proyecto creado correctamente.[/bold green]"
            )

            self.console.print(
                f"ID: [cyan]{project['id']}[/cyan]"
            )

            self.console.print(
                f"Tema: [cyan]{project['tema']}[/cyan]"
            )

            self.console.print(
                f"Ruta: [cyan]{project['path']}[/cyan]"
            )

        except Exception as error:

            Logger.error(str(error))

            self.console.print(
                f"\n[red]{error}[/red]"
            )

        self.pause()
    def continue_project_runtime(self):

        try:
            result = self.pipeline_engine.execute()

            if not result.success:
                self.console.print(
                    "\n[red]No se pudo ejecutar el Runtime.[/red]"
                )
                self.console.print(result.message)

                for error in result.errors:
                    self.console.print(f"- {error}")

                self.pause()
                return

            self.console.print(
                "\n[bold green]Runtime ejecutado correctamente.[/bold green]"
            )

            self.console.print(result.message)

            prompt_path = result.metadata.get("prompt_path")

            if prompt_path:
                self.console.print(
                    f"\nPrompt generado: [cyan]{prompt_path}[/cyan]"
                )

            data = result.data

            if isinstance(data, dict):
                completed_stage = data.get("completed_stage")
                next_stage = data.get("next_stage")

                if completed_stage:
                    self.console.print(
                        f"Stage completado: [cyan]{completed_stage}[/cyan]"
                    )

                if next_stage:
                    self.console.print(
                        f"Siguiente Stage: [cyan]{next_stage}[/cyan]"
                    )

        except Exception as error:
            Logger.error(f"Error en Runtime: {error}")
            self.console.print(f"\n[red]Error en Runtime:[/red] {error}")

        self.pause()
    def system_status(self):

        self.console.print("\n[bold cyan]Estado del Sistema[/bold cyan]\n")
        self.console.print("Versión: 0.4.0")
        self.console.print("Estado: Runtime operativo")
        self.console.print("Módulo activo: MenuController + PipelineEngine")

        self.pause()
    def validate_system(self):

        errors = self.validator.validate_system()

        if errors:

            self.console.print(
                "\n[red]Errores encontrados:[/red]"
            )

            for error in errors:
                self.console.print(f"- {error}")

        else:

            self.console.print(
                "\n[bold green]Pruebas automáticas correctas.[/bold green]"
            )

        self.pause()
        # --------------------------------------------------
    # KNOWLEDGE
    # --------------------------------------------------

    def create_knowledge_module(self):
        self.console.print(
            "\n[bold green]Crear Knowledge Module v2[/bold green]\n"
        )

        module_id = input(
            "ID del módulo, por ejemplo KM-021:\n\n> "
        ).strip()

        name = input(
            "\nNombre del módulo:\n\n> "
        ).strip()

        category = input(
            "\nCategoría [CORE]:\n\n> "
        ).strip() or "CORE"

        if not module_id or not name:
            self.console.print(
                "\n[red]El ID y el nombre son obligatorios.[/red]"
            )
            self.pause()
            return

        try:
            result = self.knowledge_builder.create_module(
                module_id=module_id,
                name=name,
                category=category,
            )

            Logger.info(
                f"Knowledge Module creado: {result['module_id']}"
            )

            self.console.print(
                "\n[bold green]Knowledge Module creado correctamente.[/bold green]"
            )
            self.console.print(
                f"ID: [cyan]{result['module_id']}[/cyan]"
            )
            self.console.print(
                f"Nombre: [cyan]{result['name']}[/cyan]"
            )
            self.console.print(
                f"Ruta: [cyan]{result['path']}[/cyan]"
            )

        except Exception as error:
            Logger.error(
                f"Error al crear Knowledge Module: {error}"
            )
            self.console.print(
                f"\n[red]Error al crear Knowledge Module:[/red] {error}"
            )

        self.pause()

    # --------------------------------------------------
    # CONFIGURACIÓN
    # --------------------------------------------------

    def configuration(self):
        self.console.print(
            "\n[yellow]Configuración estará disponible más adelante.[/yellow]"
        )
        self.pause()

    # --------------------------------------------------
    # DISPATCH
    # --------------------------------------------------

    def dispatch(self, option: str) -> bool:
        actions = {
            "1": self.new_project,
            "2": self.continue_project_runtime,
            "3": self.configuration,
            "4": self.system_status,
            "5": self.create_knowledge_module,
            "7": self.validate_system,
        }

        if option == "0":
            self.console.print(
                "\n[green]Hasta pronto.[/green]"
            )
            return False

        action = actions.get(option)

        if action is None:
            self.console.print(
                "\n[red]Opción inválida.[/red]"
            )
            self.pause()
            return True

        action()
        return True