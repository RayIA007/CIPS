"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 020
Archivo  : menu_controller.py
Estado   : RELEASE
=========================================================

Controlador principal del menú de CIPS (Adaptado al ENTREGABLE 001).
"""
import sys
import json
from pathlib import Path
from rich.console import Console

# Aseguramos que CIPS pueda encontrar la carpeta de 11_MEDIA_PRODUCTION
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "11_MEDIA_PRODUCTION"))

from media_pipeline import ejecutar_media_production
from logger import Logger
from project_manager import ProjectManager
from pipeline_engine import PipelineEngine
from validator_engine import Validator
from knowledge_module_builder import KnowledgeModuleBuilder
from runtime_constants import STAGES


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

    def update_production_status(self, project_path: Path, status: str):
        """Actualiza el archivo production.json con el estado actual."""
        prod_file = project_path / "production.json"
        if prod_file.exists():
            try:
                with open(prod_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["status"] = status
                with open(prod_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                Logger.error(f"Error actualizando estado en production.json: {e}")

    # --------------------------------------------------
    # PROYECTOS (Flujo Automatizado ENTREGABLE 001)
    # --------------------------------------------------

    def new_project(self):

        self.console.print(
            "\n[bold green]==========================================[/bold green]"
        )
        self.console.print(
            "[bold green]   CIPS - Producción Automática Audiovisual   [/bold green]"
        )
        self.console.print(
            "[bold green]==========================================[/bold green]\n"
        )

        # --------------------------------------------------
        # INTERACCIÓN 1: Pregunta inicial de entrada
        # --------------------------------------------------
        tema = input(
            "¿Qué vamos a publicar hoy?\n\n> "
        ).strip()

        if not tema:
            self.console.print(
                "\n[red]El tema no puede estar vacío.[/red]"
            )
            self.pause()
            return

        try:
            # 1. Crear workspace del proyecto
            project = self.project_manager.create_project(tema)
            project_path = Path(project['path'])

            Logger.info(f"Proyecto iniciado: {project['id']} - Tema: {project['tema']}")

            self.console.print(
                f"\n[cyan][+] Directorio creado:[/cyan] {project_path.resolve()}"
            )
            self.console.print(
                "\n[bold yellow][*] Ejecutando pipeline automático (Fase Editorial + Media Production)...[/bold yellow]\n"
            )

            # 2. Bucle automático pasando por todos los stages
            pipeline_failed = False
            stages_multimedia = {"narracion", "voz", "imagenes", "subtitulos", "ensamblado", "control_calidad"}

            for stage in STAGES:
                if stage == "final":
                    continue

                # SI ES UN STAGE EDITORIAL (Texto):
                if stage not in stages_multimedia:
                    self.console.print(f"  [bold white]--> Ejecutando Stage Editorial:[/bold white] [cyan]{stage.upper()}[/cyan]...")
                    result = self.pipeline_engine.execute()
                    if not result.success:
                        self.console.print(
                            f"\n[bold red][X] Error durante la ejecución del stage {stage}:[/bold red] {result.message}"
                        )
                        Logger.error(f"Fallo en stage {stage}: {result.message}")
                        pipeline_failed = True
                        break

                # SI LLEGAMOS A LA FASE MULTIMEDIA:
                else:
                    self.console.print(f"  [bold white]--> Ejecutando Fase Multimedia (Voz, Imágenes, Ensamblado)...[/bold white]")
                    éxito_media = ejecutar_media_production(project_path)
                    if not éxito_media:
                        pipeline_failed = True
                    # Una vez ejecutada la producción multimedia completa, salimos del bucle hacia la revisión
                    break
                        
            # Cambiar estado a READY_FOR_REVIEW al concluir la producción del video
            self.update_production_status(project_path, "READY_FOR_REVIEW")

            # --------------------------------------------------
            # INTERACCIÓN 2: Revisión final única
            # --------------------------------------------------
            short_video_path = project_path / "final" / "short.mp4"

            self.console.print(
                "\n[bold green]==========================================[/bold green]"
            )
            self.console.print(
                "[bold green] Producción terminada.[/bold green]"
            )
            self.console.print(
                f" [white]Video listo en:[/white] [cyan]{short_video_path.resolve()}[/cyan]"
            )
            self.console.print(
                "[bold green]==========================================[/bold green]\n"
            )

            self.console.print("Seleccione una opción:")
            self.console.print("  [bold cyan]1.[/bold cyan] Aprobar")
            self.console.print("  [bold cyan]2.[/bold cyan] Rehacer")
            self.console.print("  [bold cyan]3.[/bold cyan] Cancelar")

            opcion_review = input("\n> ").strip()

            if opcion_review == "1":
                self.update_production_status(project_path, "APPROVED")
                self.console.print("\n[bold green][✔] Producción APROBADA y lista para publicar.[/bold green]")
                Logger.info(f"Proyecto {project['id']} APROBADO por el usuario.")
            elif opcion_review == "2":
                self.update_production_status(project_path, "REJECTED")
                self.console.print("\n[bold yellow][↻] Producción RECHAZADA. Marcada para rehacer.[/bold yellow]")
                Logger.info(f"Proyecto {project['id']} marcado para REHACER.")
            else:
                self.update_production_status(project_path, "CANCELLED")
                self.console.print("\n[bold red][✖] Producción CANCELADA.[/bold red]")
                Logger.info(f"Proyecto {project['id']} CANCELADO por el usuario.")

        except Exception as error:
            Logger.error(str(error))
            self.console.print(
                f"\n[red]Error durante la producción:[/red] {error}"
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
        self.console.print("Versión: 0.5.0")
        self.console.print("Estado: Runtime + Media Production Operativo")
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