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

from fao_pm9_unification import FAOPM9UnificationEngine
from logger import Logger
from project_manager import ProjectManager
from pipeline_engine import PipelineEngine
from validator_engine import Validator
from knowledge_module_builder import KnowledgeModuleBuilder
from runtime_constants import STAGES


def ejecutar_media_production(proyecto_dir: Path) -> bool:
    """Carga la producción heredada únicamente cuando el operador la ejecuta."""
    from media_pipeline import ejecutar_media_production as ejecutar

    return ejecutar(proyecto_dir)


class MenuController:
    """
    Centraliza todas las acciones disponibles desde el menú principal.
    """

    def __init__(self):

        self.console = Console()

        self.project_manager = ProjectManager()
        self.pipeline_engine = PipelineEngine()
        self.fao_pm9_unification = FAOPM9UnificationEngine()
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

    @staticmethod
    def _is_fao_project(project_path: Path) -> bool:
        return (project_path / "operational_request.json").is_file()

    def _prepare_fao_project(self, project_path: Path):
        """Ejecuta FAO.5 y detiene el flujo antes de cualquier render real."""

        self.console.print(
            "  [bold white]--> Unificando con PM9:[/bold white] "
            "inventario, assets, audio, subtítulos y preparación..."
        )
        result = self.fao_pm9_unification.prepare(project_path)
        self.update_production_status(
            project_path,
            "READY_FOR_RENDER_AUTHORIZATION",
        )
        self.project_manager.checkpoint_project(
            project_path,
            label="ready_for_render_authorization",
            metadata={
                "lifecycle_state": "ready_for_render_authorization",
                **result.metadata(),
            },
        )
        self.console.print(
            "\n[bold green][OK] FAO.5 completó la preparación PM9.[/bold green]"
        )
        self.console.print(
            f"Proveedor preparado: [cyan]{result.provider}[/cyan]"
        )
        self.console.print(
            "Costo previo real: "
            f"[cyan]USD {result.total_actual_cost_usd:.2f}[/cyan]"
        )
        self.console.print(
            "Créditos estimados para un render futuro: "
            f"[cyan]{result.estimated_render_credits}[/cyan]"
        )
        self.console.print(
            f"Evidencia: [cyan]{result.evidence_path.resolve()}[/cyan]"
        )
        self.console.print(
            "[bold yellow]No se ejecutó ningún render, no inició F7 y "
            "no se publicó contenido.[/bold yellow]"
        )
        return result

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

        plataforma = input(
            "\nPlataforma [YouTube Shorts]:\n\n> "
        ).strip() or "YouTube Shorts"

        duracion_texto = input(
            "\nDuración objetivo en segundos [45]:\n\n> "
        ).strip() or "45"

        audiencia = input(
            "\nAudiencia [público general]:\n\n> "
        ).strip() or "público general"

        estilo_creativo = input(
            "\nEstilo creativo [educativo, claro y dinámico]:\n\n> "
        ).strip() or "educativo, claro y dinámico"

        try:
            duracion_segundos = int(duracion_texto)
        except ValueError:
            self.console.print(
                "\n[red]La duración debe ser un número entero de segundos.[/red]"
            )
            self.pause()
            return

        if not 1 <= duracion_segundos <= 3600:
            self.console.print(
                "\n[red]La duración debe estar entre 1 y 3600 segundos.[/red]"
            )
            self.pause()
            return

        try:
            # 1. Crear workspace del proyecto
            project = self.project_manager.create_project(
                tema,
                plataforma=plataforma,
                duracion_segundos=duracion_segundos,
                audiencia=audiencia,
                estilo_creativo=estilo_creativo,
            )
            project_path = Path(project['path'])

            Logger.info(f"Proyecto iniciado: {project['id']} - Tema: {project['tema']}")

            self.console.print(
                f"\n[cyan][+] Directorio creado:[/cyan] {project_path.resolve()}"
            )
            self.console.print(
                "[cyan][+] Checkpoint inicial guardado. "
                "El proyecto puede reanudarse desde 'Continuar Proyecto'.[/cyan]"
            )
            self.console.print(
                "\n[bold yellow][*] Ejecutando pipeline automático (Fase Editorial + Media Production)...[/bold yellow]\n"
            )

            self.project_manager.checkpoint_project(
                project_path,
                label="runtime_started",
                metadata={
                    "lifecycle_state": "editorial_in_progress",
                    "publication_performed": False,
                },
            )

            # 2. Bucle automático pasando por todos los stages
            pipeline_failed = False
            pipeline_paused = False
            production_prepared = False
            # FAO.3 conserva ``narracion`` como entregable editorial generado
            # por el proveedor LLM. La producción física comienza en ``voz``.
            stages_multimedia = {"voz", "imagenes", "subtitulos", "ensamblado", "control_calidad"}

            for stage in STAGES:
                if stage == "final":
                    continue

                # SI ES UN STAGE EDITORIAL (Texto):
                if stage not in stages_multimedia:
                    self.console.print(f"  [bold white]--> Ejecutando Stage Editorial:[/bold white] [cyan]{stage.upper()}[/cyan]...")
                    result = self.pipeline_engine.execute(
                        project_path=project_path
                    )
                    if not result.success:
                        self.console.print(
                            f"\n[bold red][X] Error durante la ejecución del stage {stage}:[/bold red] {result.message}"
                        )
                        Logger.error(f"Fallo en stage {stage}: {result.message}")
                        pipeline_failed = True
                        break
                    if result.metadata.get("requires_user_action"):
                        self.console.print(
                            "\n[bold yellow]El proyecto quedó en pausa porque "
                            "el modo manual requiere una respuesta externa.[/bold yellow]"
                        )
                        self.console.print(
                            "Usa 'Continuar Proyecto' cuando la respuesta esté disponible."
                        )
                        pipeline_paused = True
                        break

                # SI LLEGAMOS A LA FASE MULTIMEDIA:
                else:
                    editorial_package = (
                        project_path / "state" / "editorial_package.json"
                    )
                    if not editorial_package.is_file():
                        self.console.print(
                            "\n[bold red][X] La producción multimedia quedó "
                            "bloqueada: falta el paquete editorial verificable "
                            "de FAO.3.[/bold red]"
                        )
                        pipeline_failed = True
                        break
                    self.console.print(
                        "  [bold green][OK] Paquete editorial FAO.3 completo "
                        "y verificable.[/bold green]"
                    )
                    if self._is_fao_project(project_path):
                        try:
                            self._prepare_fao_project(project_path)
                            production_prepared = True
                        except Exception as error:
                            Logger.error(f"FAO.5 no pudo preparar PM9: {error}")
                            self.console.print(
                                "\n[bold red][X] FAO.5 no pudo completar la "
                                f"preparación PM9:[/bold red] {error}"
                            )
                            pipeline_failed = True
                    else:
                        self.console.print(f"  [bold white]--> Ejecutando Fase Multimedia (Voz, Imágenes, Ensamblado)...[/bold white]")
                        éxito_media = ejecutar_media_production(project_path)
                        if not éxito_media:
                            pipeline_failed = True
                    # Una vez ejecutada la producción multimedia completa, salimos del bucle hacia la revisión
                    break

            if pipeline_failed or pipeline_paused:
                self.project_manager.checkpoint_project(
                    project_path,
                    label=(
                        "runtime_paused"
                        if pipeline_paused
                        else "runtime_failed"
                    ),
                    metadata={
                        "lifecycle_state": "editorial_in_progress",
                        "requires_user_action": pipeline_paused,
                        "publication_performed": False,
                    },
                )
                if pipeline_failed:
                    self.console.print(
                        "\n[bold yellow]El proyecto conserva su checkpoint. "
                        "Puedes reintentarlo desde 'Continuar Proyecto'.[/bold yellow]"
                    )
                self.pause()
                return

            if production_prepared:
                self.pause()
                return

            # Cambiar estado a READY_FOR_REVIEW al concluir la producción del video
            self.update_production_status(project_path, "READY_FOR_REVIEW")
            self.project_manager.checkpoint_project(
                project_path,
                label="ready_for_review",
                metadata={
                    "lifecycle_state": "ready_for_review",
                    "publication_performed": False,
                },
            )

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
                self.project_manager.checkpoint_project(
                    project_path,
                    label="approved",
                    metadata={
                        "lifecycle_state": "approved",
                        "publication_performed": False,
                    },
                )
                self.console.print(
                    "\n[bold green][✔] Producción APROBADA. "
                    "La publicación no fue realizada.[/bold green]"
                )
                Logger.info(f"Proyecto {project['id']} APROBADO por el usuario.")
            elif opcion_review == "2":
                self.update_production_status(project_path, "REJECTED")
                self.project_manager.checkpoint_project(
                    project_path,
                    label="changes_requested",
                    metadata={
                        "lifecycle_state": "changes_requested",
                        "publication_performed": False,
                    },
                )
                self.console.print("\n[bold yellow][↻] Producción RECHAZADA. Marcada para rehacer.[/bold yellow]")
                Logger.info(f"Proyecto {project['id']} marcado para REHACER.")
            else:
                self.update_production_status(project_path, "CANCELLED")
                self.project_manager.checkpoint_project(
                    project_path,
                    label="cancelled",
                    metadata={
                        "lifecycle_state": "cancelled",
                        "publication_performed": False,
                    },
                )
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
            projects = self.project_manager.list_project_paths(
                resumable_only=True
            )
            if not projects:
                projects = self.project_manager.list_project_paths()

            if not projects:
                self.console.print(
                    "\n[yellow]No existe ningún proyecto para continuar.[/yellow]"
                )
                self.pause()
                return

            self.console.print(
                "\n[bold cyan]Proyectos disponibles para continuar[/bold cyan]\n"
            )
            for index, path in enumerate(projects, start=1):
                project = self.project_manager.load_project(path)
                self.console.print(
                    f"  [cyan]{index}.[/cyan] {project.project_id} — "
                    f"{project.tema} — stage: {project.stage_actual}"
                )

            selection = input(
                f"\nSelecciona un proyecto [último: {len(projects)}]:\n\n> "
            ).strip()
            if selection:
                try:
                    selected_index = int(selection)
                except ValueError:
                    selected_index = 0
            else:
                selected_index = len(projects)

            if not 1 <= selected_index <= len(projects):
                self.console.print(
                    "\n[red]La selección del proyecto no es válida.[/red]"
                )
                self.pause()
                return

            project_path = projects[selected_index - 1]
            selected_project = self.project_manager.load_project(project_path)
            self.project_manager.checkpoint_project(
                project_path,
                label="resume_requested",
                metadata={
                    "lifecycle_state": "editorial_in_progress",
                    "resumed_stage": selected_project.stage_actual,
                    "publication_performed": False,
                },
            )

            if (
                self._is_fao_project(project_path)
                and selected_project.stage_actual
                in {
                    "voz",
                    "imagenes",
                    "subtitulos",
                    "ensamblado",
                    "control_calidad",
                }
            ):
                try:
                    self._prepare_fao_project(project_path)
                except Exception as error:
                    Logger.error(f"FAO.5 no pudo reanudar PM9: {error}")
                    self.project_manager.checkpoint_project(
                        project_path,
                        label="resume_failed",
                        metadata={
                            "lifecycle_state": "production_preparation_failed",
                            "publication_performed": False,
                        },
                    )
                    self.console.print(
                        "\n[red]No se pudo completar la preparación PM9.[/red]"
                    )
                    self.console.print(str(error))
                self.pause()
                return

            result = self.pipeline_engine.execute(
                project_path=project_path
            )

            if not result.success:
                self.console.print(
                    "\n[red]No se pudo ejecutar el Runtime.[/red]"
                )
                self.console.print(result.message)

                for error in result.errors:
                    self.console.print(f"- {error}")

                self.project_manager.checkpoint_project(
                    project_path,
                    label="resume_failed",
                    metadata={
                        "lifecycle_state": "editorial_in_progress",
                        "publication_performed": False,
                    },
                )

                self.pause()
                return

            self.project_manager.checkpoint_project(
                project_path,
                label="runtime_step_completed",
                metadata={
                    "lifecycle_state": "editorial_in_progress",
                    "completed_stage": result.metadata.get(
                        "completed_stage",
                        "",
                    ),
                    "next_stage": result.metadata.get(
                        "next_stage",
                        selected_project.stage_actual,
                    ),
                    "requires_user_action": result.metadata.get(
                        "requires_user_action",
                        False,
                    ),
                    "publication_performed": False,
                },
            )

            self.console.print(
                "\n[bold green]Runtime ejecutado correctamente.[/bold green]"
            )

            self.console.print(result.message)
            self.console.print(
                f"Proyecto reanudado: [cyan]{project_path.name}[/cyan]"
            )

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
