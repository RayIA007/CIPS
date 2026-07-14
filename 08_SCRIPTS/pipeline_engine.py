"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 055
Archivo  : pipeline_engine.py
Estado   : RELEASE
=========================================================

Adaptador operativo entre la interfaz de CIPS y el
Runtime Framework.

Responsabilidades:
- cargar el proyecto activo;
- detectar una respuesta manual existente;
- construir RuntimeContext;
- ejecutar el pipeline previo al LLM;
- solicitar respuesta mediante LLMAdapter;
- persistir respuestas automáticas;
- conservar el modo manual;
- validar respuestas;
- actualizar memoria;
- avanzar el Stage aprobado.
"""

from pathlib import Path

from context_compressor import ContextCompressor
from export_engine import ExportEngine
from final_project_builder import FinalProjectBuilder
from finalization_engine import FinalizationEngine
from context_engine import ContextEngine
from knowledge_engine import KnowledgeEngine
from knowledge_resolver import KnowledgeResolver
from llm_adapter import LLMAdapter
from manifest_engine import ManifestEngine
from memory_engine import MemoryEngine
from metrics_engine import MetricsEngine
from pipeline_runner import PipelineRunner
from project_manager import ProjectManager
from prompt_engine import PromptEngine
from runtime_constants import FINAL_STAGE, STAGES, STAGE_FILES
from runtime_context import RuntimeContext
from runtime_models import EngineResult, LLMResponse, Project
from validator_engine import ValidatorEngine


class PipelineEngine:
    """
    Punto de coordinación operativo del Runtime de CIPS.

    Mantiene la interfaz pública utilizada por MenuController:

        PipelineEngine().execute()

    El trabajo interno se delega a RuntimeContext,
    PipelineRunner y LLMAdapter.
    """

    component_name = "pipeline_engine"

    def __init__(self) -> None:
        self.project_manager = ProjectManager()
        self.llm_adapter = LLMAdapter()

        self.final_project_builder = FinalProjectBuilder(
            project_manager=self.project_manager
        )
        self.finalization_engine = FinalizationEngine()
        self.manifest_engine = ManifestEngine()
        self.metrics_engine = MetricsEngine()
        self.export_engine = ExportEngine()

        self.pre_llm_runner = PipelineRunner(
            components=[
                KnowledgeEngine(),
                KnowledgeResolver(),
                ContextCompressor(),
                ContextEngine(),
                PromptEngine(),
            ]
        )

        self.post_llm_runner = PipelineRunner(
            components=[
                ValidatorEngine(),
                MemoryEngine(),
            ]
        )

    def execute(
        self,
        project_path: Path | None = None,
    ) -> EngineResult:
        """
        Ejecuta la acción requerida por el proyecto activo.

        Flujo:

        1. Si el proyecto está en FINAL, informa su cierre.
        2. Si existe una respuesta manual, la valida y avanza.
        3. Si no existe respuesta, genera el prompt.
        4. Ejecuta LLMAdapter.
        5. Si el proveedor es manual, espera intervención.
        6. Si el proveedor responde automáticamente:
           - guarda la respuesta en el archivo del Stage;
           - valida;
           - actualiza memoria;
           - avanza el Stage.
        """

        try:
            project = self.project_manager.load_project(
                project_path
            )

            if project.stage_actual == FINAL_STAGE:
                return EngineResult.ok(
                    data=project,
                    message=(
                        "El proyecto ya se encuentra "
                        "en la etapa final."
                    ),
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                        "finished": True,
                    },
                )

            response_path = self._get_response_path(
                project
            )

            response_content = self._read_response(
                response_path
            )

            if response_content:
                return self._process_manual_response(
                    project=project,
                    response_content=response_content,
                    response_path=response_path,
                )

            return self._generate_and_request_response(
                project
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en PipelineEngine."
                ),
                errors=[str(error)],
                metadata={
                    "component": self.component_name,
                },
            )

    def _generate_and_request_response(
        self,
        project: Project,
    ) -> EngineResult:
        """
        Genera el prompt y lo entrega al proveedor configurado.
        """

        runtime_context = RuntimeContext(
            project=project
        )

        pre_result = self.pre_llm_runner.execute(
            runtime_context
        )

        if not pre_result.success:
            return pre_result

        if not runtime_context.prompt_path:
            return EngineResult.fail(
                message=(
                    "El Runtime terminó sin generar "
                    "un archivo de prompt."
                ),
                errors=[
                    "RuntimeContext.prompt_path vacío."
                ],
                metadata=self._base_metadata(
                    project
                ),
            )

        adapter_result = self.llm_adapter.execute(
            runtime_context
        )

        if adapter_result.success:
            if runtime_context.llm_response is None:
                return EngineResult.fail(
                    message=(
                        "LLMAdapter terminó correctamente, "
                        "pero no generó una respuesta."
                    ),
                    errors=[
                        "RuntimeContext.llm_response vacío."
                    ],
                    metadata=self._base_metadata(
                        project
                    ),
                )

            persistence_result = (
                self._persist_automatic_response(
                    runtime_context
                )
            )

            if not persistence_result.success:
                return persistence_result

            runtime_context.register_result(
                "response_persistence",
                persistence_result,
            )

            return self._validate_and_advance(
                runtime_context
            )

        requires_user_action = bool(
            adapter_result.metadata.get(
                "requires_user_action",
                False,
            )
        )

        if requires_user_action:
            return self._build_manual_pending_result(
                runtime_context=runtime_context,
                adapter_result=adapter_result,
                pre_result=pre_result,
            )

        return EngineResult.fail(
            message=adapter_result.message,
            errors=list(
                adapter_result.errors
            ),
            warnings=list(
                adapter_result.warnings
            ),
            metadata={
                **self._base_metadata(project),
                **adapter_result.metadata,
                "prompt_path": runtime_context.prompt_path,
            },
        )

    def _persist_automatic_response(
        self,
        runtime_context: RuntimeContext,
    ) -> EngineResult:
        """
        Guarda de forma segura la respuesta automática.

        La escritura se realiza primero en un archivo temporal.
        Después se reemplaza el archivo oficial del Stage para
        reducir el riesgo de dejar contenido incompleto.
        """

        project = runtime_context.project
        llm_response = runtime_context.llm_response

        if llm_response is None:
            return EngineResult.fail(
                message=(
                    "No existe una respuesta automática "
                    "para guardar."
                ),
                errors=[
                    "RuntimeContext.llm_response vacío."
                ],
                metadata=self._base_metadata(
                    project
                ),
            )

        response_content = (
            llm_response.content
            or ""
        ).strip()

        if not response_content:
            return EngineResult.fail(
                message=(
                    "La respuesta automática está vacía "
                    "y no puede guardarse."
                ),
                errors=[
                    "LLMResponse.content vacío."
                ],
                metadata=self._base_metadata(
                    project
                ),
            )

        response_path = self._get_response_path(
            project
        )

        temporary_path = response_path.with_suffix(
            f"{response_path.suffix}.tmp"
        )

        try:
            response_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            temporary_path.write_text(
                response_content + "\n",
                encoding="utf-8",
            )

            temporary_path.replace(
                response_path
            )

        except Exception as error:
            if temporary_path.exists():
                temporary_path.unlink(
                    missing_ok=True
                )

            return EngineResult.fail(
                message=(
                    "No fue posible guardar la respuesta "
                    "automática del Stage."
                ),
                errors=[str(error)],
                metadata={
                    **self._base_metadata(project),
                    "response_path": str(response_path),
                },
            )

        runtime_context.metadata[
            "automatic_response"
        ] = {
            "persisted": True,
            "response_path": str(response_path),
            "characters": len(response_content),
            "provider": (
                llm_response.metadata.get(
                    "provider",
                    self.llm_adapter.get_provider().provider_name,
                )
            ),
            "model": llm_response.model,
        }

        return EngineResult.ok(
            data={
                "response_path": str(response_path),
                "characters": len(response_content),
            },
            message=(
                "Respuesta automática guardada "
                "correctamente."
            ),
            metadata={
                **self._base_metadata(project),
                "response_path": str(response_path),
                "characters": len(response_content),
                "provider": (
                    llm_response.metadata.get(
                        "provider",
                        self.llm_adapter.get_provider().provider_name,
                    )
                ),
                "model": llm_response.model,
            },
        )

    def _process_manual_response(
        self,
        project: Project,
        response_content: str,
        response_path: Path,
    ) -> EngineResult:
        """
        Convierte una respuesta guardada en LLMResponse.
        """

        runtime_context = RuntimeContext(
            project=project
        )

        runtime_context.llm_response = LLMResponse(
            content=response_content,
            model="external_manual",
            metadata={
                "provider": "manual",
                "mode": "saved_file",
                "project_id": project.project_id,
                "stage": project.stage_actual,
                "response_path": str(response_path),
            },
        )

        return self._validate_and_advance(
            runtime_context
        )

    def _validate_and_advance(
        self,
        runtime_context: RuntimeContext,
    ) -> EngineResult:
        """
        Ejecuta validación, memoria y transición de Stage.
        """

        project = runtime_context.project

        post_result = self.post_llm_runner.execute(
            runtime_context
        )

        if not post_result.success:
            return post_result

        validation_result = (
            runtime_context.validation_result
        )

        if (
            validation_result is None
            or not validation_result.approved
        ):
            return EngineResult.fail(
                message=(
                    "La respuesta no fue aprobada. "
                    "El proyecto permanecerá en el "
                    "Stage actual."
                ),
                errors=(
                    list(validation_result.errors)
                    if validation_result
                    else [
                        "ValidationResult no disponible."
                    ]
                ),
                warnings=(
                    list(validation_result.warnings)
                    if validation_result
                    else []
                ),
                metadata=self._base_metadata(
                    project
                ),
            )

        completed_stage = project.stage_actual
        next_stage = self._get_next_stage(
            completed_stage
        )

        finalization_result = None

        if next_stage == FINAL_STAGE:
            finalization_result = (
                self._finalize_and_export(
                    project
                )
            )

            if not finalization_result.success:
                return EngineResult.fail(
                    message=(
                        "El Stage 'publicacion' fue validado, "
                        "pero falló la finalización y exportación. "
                        "El proyecto permanecerá en 'publicacion'."
                    ),
                    errors=list(
                        finalization_result.errors
                    ),
                    warnings=[
                        *runtime_context.warnings,
                        *finalization_result.warnings,
                    ],
                    metadata={
                        **self._base_metadata(project),
                        **finalization_result.metadata,
                        "completed_stage": completed_stage,
                        "next_stage": next_stage,
                        "finalization_failed": True,
                    },
                )

        self.project_manager.update_project_stage(
            project=project,
            next_stage=next_stage,
        )

        response_path = self._get_response_path_for_stage(
            project=project,
            stage=completed_stage,
        )

        result_data = {
            "project_id": project.project_id,
            "completed_stage": completed_stage,
            "next_stage": next_stage,
            "memory_data": runtime_context.memory_data,
            "llm_response": runtime_context.llm_response,
            "response_path": str(response_path),
        }

        result_metadata = {
            **self._base_metadata(project),
            "completed_stage": completed_stage,
            "next_stage": next_stage,
            "response_path": str(response_path),
            "response_persisted": (
                response_path.exists()
                and response_path.stat().st_size > 0
            ),
            "provider": (
                self.llm_adapter
                .get_provider()
                .provider_name
            ),
            "model": (
                self.llm_adapter
                .get_provider()
                .model_name
            ),
            "executed_components": (
                post_result.metadata.get(
                    "executed_components",
                    [],
                )
            ),
        }

        if finalization_result is not None:
            result_data[
                "final_project"
            ] = finalization_result.data

            result_metadata[
                "finalization"
            ] = finalization_result.metadata

        message = (
            f"Stage '{completed_stage}' validado. "
            f"Nuevo Stage: '{next_stage}'."
        )

        if finalization_result is not None:
            message += (
                " Proyecto finalizado y paquete "
                "de exportación generado."
            )

        return EngineResult.ok(
            data=result_data,
            message=message,
            warnings=list(
                runtime_context.warnings
            ),
            metadata=result_metadata,
        )

    def _finalize_and_export(
        self,
        project: Project,
    ) -> EngineResult:
        """
        Ejecuta la cadena automática de finalización.

        El Stage se establece temporalmente en ``final`` dentro
        del objeto en memoria para que los artefactos registren
        el estado definitivo. ``proyecto.yaml`` solo se actualiza
        después de que toda la cadena termina correctamente.
        """

        original_stage = project.stage_actual
        project.stage_actual = FINAL_STAGE

        builder_result = (
            self.final_project_builder.execute(
                project_input=project,
                require_complete=True,
            )
        )

        if not builder_result.success:
            project.stage_actual = original_stage
            return self._build_finalization_failure(
                project=project,
                component="final_project_builder",
                result=builder_result,
            )

        final_project = builder_result.data

        finalization_result = (
            self.finalization_engine.execute(
                final_project
            )
        )

        if not finalization_result.success:
            project.stage_actual = original_stage
            return self._build_finalization_failure(
                project=project,
                component="finalization_engine",
                result=finalization_result,
            )

        final_project = finalization_result.data

        manifest_result = (
            self.manifest_engine.execute(
                final_project
            )
        )

        if not manifest_result.success:
            project.stage_actual = original_stage
            return self._build_finalization_failure(
                project=project,
                component="manifest_engine",
                result=manifest_result,
            )

        final_project = manifest_result.data

        metrics_result = (
            self.metrics_engine.execute(
                final_project
            )
        )

        if not metrics_result.success:
            project.stage_actual = original_stage
            return self._build_finalization_failure(
                project=project,
                component="metrics_engine",
                result=metrics_result,
            )

        final_project = metrics_result.data

        export_result = self.export_engine.execute(
            final_project=final_project,
            formats=[
                "markdown",
                "json",
                "zip",
            ],
            output_directory=(
                project.path
                / "06_EXPORTACIONES"
            ),
            stop_on_error=True,
        )

        if not export_result.success:
            project.stage_actual = original_stage
            return self._build_finalization_failure(
                project=project,
                component="export_engine",
                result=export_result,
            )

        final_project = export_result.data

        return EngineResult.ok(
            data=final_project,
            message=(
                "Finalización y exportación automáticas "
                "completadas correctamente."
            ),
            warnings=[
                *builder_result.warnings,
                *finalization_result.warnings,
                *manifest_result.warnings,
                *metrics_result.warnings,
                *export_result.warnings,
            ],
            metadata={
                **self._base_metadata(project),
                "finalized": True,
                "exports": dict(
                    final_project.exports
                ),
                "export_formats": [
                    "markdown",
                    "json",
                    "zip",
                ],
                "components": [
                    "final_project_builder",
                    "finalization_engine",
                    "manifest_engine",
                    "metrics_engine",
                    "export_engine",
                ],
            },
        )

    def _build_finalization_failure(
        self,
        project: Project,
        component: str,
        result: EngineResult,
    ) -> EngineResult:
        """
        Normaliza un fallo de la cadena de finalización.
        """

        return EngineResult.fail(
            message=(
                "Pipeline detenido durante la finalización "
                f"en '{component}': {result.message}"
            ),
            errors=list(
                result.errors
            ),
            warnings=list(
                result.warnings
            ),
            metadata={
                **self._base_metadata(project),
                **result.metadata,
                "failed_component": component,
                "finalization_failed": True,
            },
        )

    def _build_manual_pending_result(
        self,
        runtime_context: RuntimeContext,
        adapter_result: EngineResult,
        pre_result: EngineResult,
    ) -> EngineResult:
        """
        Convierte la espera manual en un resultado operativo exitoso.

        La ejecución no falló técnicamente. El Runtime generó
        correctamente el prompt y ahora necesita intervención.
        """

        project = runtime_context.project

        response_path = self._get_response_path(
            project
        )

        return EngineResult.ok(
            data={
                "project_id": project.project_id,
                "stage": project.stage_actual,
                "prompt_object": runtime_context.prompt_object,
                "prompt_markdown": runtime_context.prompt_markdown,
                "prompt_path": runtime_context.prompt_path,
                "response_path": str(response_path),
                "requires_user_action": True,
            },
            message=(
                "Prompt generado. Copia el prompt en la IA "
                "y guarda la respuesta en el archivo del "
                "Stage actual."
            ),
            warnings=list(
                adapter_result.warnings
            ),
            metadata={
                **self._base_metadata(project),
                "prompt_path": runtime_context.prompt_path,
                "response_path": str(response_path),
                "characters": len(
                    runtime_context.prompt_markdown
                ),
                "requires_user_action": True,
                "provider": (
                    self.llm_adapter
                    .get_provider()
                    .provider_name
                ),
                "model": (
                    self.llm_adapter
                    .get_provider()
                    .model_name
                ),
                "executed_components": (
                    pre_result.metadata.get(
                        "executed_components",
                        [],
                    )
                ),
            },
        )

    def _get_response_path(
        self,
        project: Project,
    ) -> Path:
        """
        Devuelve el archivo asociado al Stage actual.
        """

        return self._get_response_path_for_stage(
            project=project,
            stage=project.stage_actual,
        )

    def _get_response_path_for_stage(
        self,
        project: Project,
        stage: str,
    ) -> Path:
        """
        Devuelve el archivo asociado a un Stage específico.
        """

        filename = STAGE_FILES.get(
            stage
        )

        if filename is None:
            raise ValueError(
                "El Stage no tiene un archivo asociado: "
                f"{stage}"
            )

        return project.path / filename

    def _read_response(
        self,
        response_path: Path,
    ) -> str:
        """
        Lee la respuesta guardada para el Stage actual.
        """

        if not response_path.exists():
            return ""

        content = response_path.read_text(
            encoding="utf-8"
        ).strip()

        if not content:
            return ""

        placeholder_markers = [
            "pendiente",
            "por completar",
            "aquí va",
            "contenido pendiente",
        ]

        lowered_content = content.lower()

        if (
            len(content) < 200
            and any(
                marker in lowered_content
                for marker in placeholder_markers
            )
        ):
            return ""

        return content

    def _get_next_stage(
        self,
        current_stage: str,
    ) -> str:
        """
        Devuelve el siguiente Stage oficial.
        """

        if current_stage not in STAGES:
            return FINAL_STAGE

        index = STAGES.index(
            current_stage
        )

        if index + 1 >= len(STAGES):
            return FINAL_STAGE

        return STAGES[index + 1]

    def _base_metadata(
        self,
        project: Project,
    ) -> dict:
        """
        Construye metadatos comunes del Pipeline.
        """

        return {
            "component": self.component_name,
            "project_id": project.project_id,
            "stage": project.stage_actual,
        }