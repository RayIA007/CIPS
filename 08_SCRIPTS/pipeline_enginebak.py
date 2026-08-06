"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 062
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
import time

from context_compressor import ContextCompressor
from context_engine import ContextEngine
from export_engine import ExportEngine
from final_project_builder import FinalProjectBuilder
from finalization_engine import FinalizationEngine
from intelligence_pipeline import IntelligencePipeline
from knowledge_engine import KnowledgeEngine
from knowledge_resolver import KnowledgeResolver
from llm_adapter import LLMAdapter
from manifest_engine import ManifestEngine
from memory_engine import MemoryEngine
from metrics_engine import MetricsEngine
from pipeline_runner import PipelineRunner
from project_manager import ProjectManager
from prompt_engine import PromptEngine
from runtime_constants import (
    FINAL_STAGE,
    STAGES,
    STAGE_FILES,
)
from runtime_context import RuntimeContext
from runtime_models import (
    EngineResult,
    LLMResponse,
    Project,
)
from telemetry_engine import TelemetryEngine
from telemetry_models import (
    TelemetryAttempt,
    TelemetryEvent,
)
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

    def __init__(self, stage_delay_seconds: float = 12.0) -> None:
        self.stage_delay_seconds = stage_delay_seconds
        self.project_manager = ProjectManager()
        self.llm_adapter = LLMAdapter()

        self.final_project_builder = FinalProjectBuilder(
            project_manager=self.project_manager
        )
        self.finalization_engine = FinalizationEngine()
        self.manifest_engine = ManifestEngine()
        self.metrics_engine = MetricsEngine()
        self.export_engine = ExportEngine()
        self.telemetry_engine = TelemetryEngine()
                
        # --------------------------------------------------
        # Intelligence Framework
        # --------------------------------------------------
        
        self.intelligence_pipeline = IntelligencePipeline(
            telemetry_engine=self.telemetry_engine
        )
                
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

        Además registra un TelemetryEvent para cada Stage
        ejecutado, tanto en éxito como en fallo. Un problema
        de telemetría nunca invalida el resultado operativo
        del Pipeline.
        """

        started_at = time.perf_counter()
        project: Project | None = None
        executed_stage = ""

        try:
            project = self.project_manager.load_project(
                project_path
            )

            executed_stage = project.stage_actual

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
                result = self._process_manual_response(
                    project=project,
                    response_content=response_content,
                    response_path=response_path,
                )
            else:
                result = self._generate_and_request_response(
                    project
                )

                if result.success and self.stage_delay_seconds > 0:
                    time.sleep(self.stage_delay_seconds)
                    
        except Exception as error:
            result = EngineResult.fail(
                message=(
                    "Error inesperado en PipelineEngine."
                ),
                errors=[str(error)],
                metadata={
                    "component": self.component_name,
                },
            )

        if (
            project is None
            or executed_stage == FINAL_STAGE
        ):
            return result

        duration_seconds = round(
            time.perf_counter() - started_at,
            6,
        )

        result = self._attach_telemetry(
            project=project,
            stage=executed_stage,
            result=result,
            duration_seconds=duration_seconds,
        )
        if (
            result.success
            and executed_stage == "publicacion"
            and result.metadata.get(
                "next_stage"
            ) == FINAL_STAGE
        ):
            result = self._attach_intelligence_package(
                project=project,
                result=result,
            )
        return result


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
            validation_metadata = (
                dict(validation_result.metadata)
                if validation_result
                else {}
            )

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
                metadata={
                    **self._base_metadata(project),
                    "validation_score": (
                        validation_metadata.get(
                            "score"
                        )
                    ),
                    "validation_passing_score": (
                        validation_metadata.get(
                            "passing_score"
                        )
                    ),
                    "validation_approved": False,
                },
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
            "runtime_context": runtime_context,
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
            "validation_score": (
                validation_result.metadata.get(
                    "score"
                )
            ),
            "validation_passing_score": (
                validation_result.metadata.get(
                    "passing_score"
                )
            ),
            "validation_approved": True,
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

    def _attach_telemetry(
        self,
        project: Project,
        stage: str,
        result: EngineResult,
        duration_seconds: float,
    ) -> EngineResult:
        """
        Registra telemetría sin alterar el éxito operativo.

        Si TelemetryEngine falla, el resultado original se
        conserva y recibe una advertencia diagnóstica.
        """

        telemetry_result = self._record_telemetry(
            project=project,
            stage=stage,
            result=result,
            duration_seconds=duration_seconds,
        )

        result.metadata[
            "telemetry"
        ] = dict(
            telemetry_result.metadata
        )

        if telemetry_result.success:
            result.metadata[
                "telemetry_recorded"
            ] = True
            return result

        result.metadata[
            "telemetry_recorded"
        ] = False

        telemetry_warning = (
            "El Pipeline terminó, pero no fue posible "
            "registrar su telemetría: "
            + telemetry_result.message
        )

        result.warnings.append(
            telemetry_warning
        )

        return result


    def _attach_intelligence_package(
        self,
        project: Project,
        result: EngineResult,
    ) -> EngineResult:
        """
        Genera el paquete de inteligencia del proyecto finalizado.

        La inteligencia es una operación posterior al Pipeline.
        Un fallo en este componente no invalida una ejecución
        operativa que ya terminó correctamente.
        """

        intelligence_result = (
            self.intelligence_pipeline.execute(
                project_path=project.path,
                project_id=project.project_id,
                persist=True,
            )
        )

        result.metadata[
            "intelligence"
        ] = dict(
            intelligence_result.metadata
        )

        if intelligence_result.success:
            result.metadata[
                "intelligence_package_generated"
            ] = True

            if isinstance(
                result.data,
                dict,
            ):
                result.data[
                    "intelligence_package"
                ] = intelligence_result.data

            return result

        result.metadata[
            "intelligence_package_generated"
        ] = False

        result.metadata[
            "intelligence_failed_component"
        ] = intelligence_result.metadata.get(
            "failed_component",
            "",
        )

        intelligence_warning = (
            "El proyecto terminó correctamente, "
            "pero no fue posible generar el paquete "
            "de inteligencia: "
            f"{intelligence_result.message}"
        )

        result.warnings.append(
            intelligence_warning
        )

        for warning in intelligence_result.warnings:
            if warning not in result.warnings:
                result.warnings.append(
                    warning
                )

        return result


    def _record_telemetry(
        self,
        project: Project,
        stage: str,
        result: EngineResult,
        duration_seconds: float,
    ) -> EngineResult:
        """
        Convierte EngineResult, RuntimeContext, LLMAdapter y
        LLMResponse en un TelemetryEvent consolidado.
        """

        result_metadata = (
            dict(result.metadata)
            if isinstance(
                result.metadata,
                dict,
            )
            else {}
        )

        runtime_context = None
        llm_response = None

        if isinstance(
            result.data,
            dict,
        ):
            runtime_context = result.data.get(
                "runtime_context"
            )

            llm_response = result.data.get(
                "llm_response"
            )

        # --------------------------------------------------
        # Metadata de LLMResponse
        # --------------------------------------------------

        response_metadata: dict = {}

        if llm_response is not None:
            raw_response_metadata = getattr(
                llm_response,
                "metadata",
                {},
            )

            if isinstance(
                raw_response_metadata,
                dict,
            ):
                response_metadata = dict(
                    raw_response_metadata
                )

        # --------------------------------------------------
        # Metadata de LLMAdapter registrada en RuntimeContext
        # --------------------------------------------------

        adapter_metadata: dict = {}

        if isinstance(
            runtime_context,
            RuntimeContext,
        ):
            adapter_result = None

            get_result = getattr(
                runtime_context,
                "get_result",
                None,
            )

            if callable(
                get_result
            ):
                adapter_result = get_result(
                    "llm_adapter"
                )

            else:
                component_results = getattr(
                    runtime_context,
                    "component_results",
                    {},
                )

                if isinstance(
                    component_results,
                    dict,
                ):
                    adapter_result = component_results.get(
                        "llm_adapter"
                    )

            if (
                adapter_result is not None
                and isinstance(
                    getattr(
                        adapter_result,
                        "metadata",
                        None,
                    ),
                    dict,
                )
            ):
                adapter_metadata = dict(
                    adapter_result.metadata
                )

        # El resultado final del Pipeline tiene mayor prioridad.
        metadata = {
            **response_metadata,
            **adapter_metadata,
            **result_metadata,
        }

        # --------------------------------------------------
        # Retry
        # --------------------------------------------------

        retry_metadata = metadata.get(
            "retry",
            {},
        )

        if not isinstance(
            retry_metadata,
            dict,
        ):
            retry_metadata = {}

        raw_attempts = retry_metadata.get(
            "attempts",
            [],
        )

        if not isinstance(
            raw_attempts,
            list,
        ):
            raw_attempts = []

        attempts = [
            TelemetryAttempt(
                attempt_number=attempt.get(
                    "attempt_number",
                    1,
                ),
                success=attempt.get(
                    "success",
                    False,
                ),
                duration_seconds=attempt.get(
                    "duration_seconds",
                    0.0,
                ),
                delay_seconds=attempt.get(
                    "delay_seconds",
                    0.0,
                ),
                retryable=attempt.get(
                    "retryable",
                    False,
                ),
                status_code=attempt.get(
                    "status_code"
                ),
                exception_type=attempt.get(
                    "exception_type",
                    "",
                ),
                matched_rule=attempt.get(
                    "matched_rule",
                    "",
                ),
                message=attempt.get(
                    "message",
                    "",
                ),
                metadata=attempt.get(
                    "metadata",
                    {},
                ),
            )
            for attempt in raw_attempts
            if isinstance(
                attempt,
                dict,
            )
        ]

        response_content = ""

        if llm_response is not None:
            response_content = str(
                getattr(
                    llm_response,
                    "content",
                    "",
                )
                or ""
            )

        retry_attempts = int(
            metadata.get(
                "retry_attempts",
                retry_metadata.get(
                    "attempts_count",
                    len(attempts),
                ),
            )
            or 0
        )

        retry_count = int(
            metadata.get(
                "retry_count",
                retry_metadata.get(
                    "retries_count",
                    max(
                        retry_attempts - 1,
                        0,
                    ),
                ),
            )
            or 0
        )

        # --------------------------------------------------
        # Evento
        # --------------------------------------------------

        event = TelemetryEvent(
            event_id="",
            timestamp="",
            project_id=project.project_id,
            component=self.component_name,
            operation="execute_stage",
            stage=stage,
            event_type="stage_execution",
            success=result.success,
            message=result.message,
            provider=str(
                metadata.get(
                    "provider",
                    "",
                )
            ),
            model=str(
                metadata.get(
                    "model",
                    (
                        getattr(
                            llm_response,
                            "model",
                            "",
                        )
                        if llm_response is not None
                        else ""
                    ),
                )
            ),
            thinking_level=str(
                metadata.get(
                    "thinking_level",
                    "",
                )
            ),
            duration_seconds=duration_seconds,
            prompt_characters=int(
                metadata.get(
                    "prompt_characters",
                    0,
                )
                or 0
            ),
            response_characters=int(
                metadata.get(
                    "response_characters",
                    len(
                        response_content
                    ),
                )
                or 0
            ),
            prompt_tokens=int(
                metadata.get(
                    "prompt_tokens",
                    0,
                )
                or 0
            ),
            response_tokens=int(
                metadata.get(
                    "response_tokens",
                    0,
                )
                or 0
            ),
            thinking_tokens=int(
                metadata.get(
                    "thinking_tokens",
                    0,
                )
                or 0
            ),
            total_tokens=int(
                metadata.get(
                    "total_tokens",
                    0,
                )
                or 0
            ),
            retry_enabled=bool(
                metadata.get(
                    "retry_enabled",
                    bool(
                        retry_metadata
                    ),
                )
            ),
            retry_attempts=retry_attempts,
            retry_count=retry_count,
            retry_exhausted=bool(
                metadata.get(
                    "retry_exhausted",
                    retry_metadata.get(
                        "exhausted",
                        False,
                    ),
                )
            ),
            succeeded_after_retry=bool(
                metadata.get(
                    "succeeded_after_retry",
                    retry_metadata.get(
                        "succeeded_after_retry",
                        False,
                    ),
                )
            ),
            status_code=metadata.get(
                "status_code"
            ),
            exception_type=str(
                metadata.get(
                    "exception_type",
                    "",
                )
            ),
            validation_score=metadata.get(
                "validation_score"
            ),
            validation_passing_score=metadata.get(
                "validation_passing_score"
            ),
            validation_approved=metadata.get(
                "validation_approved"
            ),
            attempts=attempts,
            warnings=list(
                result.warnings
            ),
            errors=list(
                result.errors
            ),
            metadata={
                "next_stage": metadata.get(
                    "next_stage",
                    stage,
                ),
                "response_path": metadata.get(
                    "response_path",
                    "",
                ),
                "prompt_path": metadata.get(
                    "prompt_path",
                    "",
                ),
                "retry_total_duration_seconds": (
                    retry_metadata.get(
                        "total_duration_seconds"
                    )
                ),
                "finished": metadata.get(
                    "finished",
                    False,
                ),
                "adapter_metadata_available": bool(
                    adapter_metadata
                ),
            },
        )

        return self.telemetry_engine.execute(
            event=event,
            project_path=project.path,
            update_summary=True,
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