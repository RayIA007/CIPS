"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 025
Archivo  : memory_engine.py
Estado   : RELEASE
=========================================================

Registra en memoria los Stages aprobados y conserva la
trazabilidad del proyecto.

Compatibilidad:
- PipelineEngine mediante execute(Project, ValidationResult).
- PipelineRunner mediante execute(RuntimeContext).
"""

from runtime_component import RuntimeComponent
from runtime_constants import FINAL_STAGE, STAGES
from runtime_context import RuntimeContext
from runtime_models import (
    EngineResult,
    MemoryRecord,
    Project,
    ValidationResult,
)
from utils import (
    current_datetime,
    read_yaml,
    write_yaml,
)


class MemoryEngine(RuntimeComponent):
    """
    Actualiza la memoria después de una validación aprobada.

    Admite dos formas de ejecución:

    1. execute(Project, ValidationResult)
       Mantiene compatibilidad con PipelineEngine.

    2. execute(RuntimeContext)
       Implementa el contrato del Runtime Framework.
    """

    component_name = "memory_engine"

    def execute(
        self,
        runtime_input: Project | RuntimeContext,
        validation: ValidationResult | None = None,
    ) -> EngineResult:
        """
        Registra el Stage validado y calcula el siguiente Stage.
        """

        try:
            runtime_context = self._get_runtime_context(
                runtime_input
            )

            project = self._get_project(
                runtime_input
            )

            validation_result = self._get_validation_result(
                runtime_input=runtime_input,
                validation=validation,
            )

            if validation_result is None:
                return EngineResult.fail(
                    message=(
                        "No existe un ValidationResult "
                        "disponible para actualizar memoria."
                    ),
                    errors=[
                        "ValidationResult no disponible."
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            if not validation_result.approved:
                return EngineResult.fail(
                    message=(
                        "No se puede actualizar memoria con "
                        "una validación rechazada."
                    ),
                    errors=list(
                        validation_result.errors
                    ),
                    warnings=list(
                        validation_result.warnings
                    ),
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            memory_path = (
                project.path
                / "memoria.yaml"
            )

            current_memory = read_yaml(
                memory_path
            )

            if not isinstance(
                current_memory,
                dict,
            ):
                current_memory = {}

            records = current_memory.get(
                "historial",
                [],
            )

            if not isinstance(
                records,
                list,
            ):
                records = []

            next_stage = self._get_next_stage(
                project.stage_actual
            )

            timestamp = current_datetime()

            record = MemoryRecord(
                stage=project.stage_actual,
                status="completed",
                summary=(
                    f"Stage {project.stage_actual} "
                    "validado correctamente."
                ),
                next_stage=next_stage,
                metadata={
                    "project_id": project.project_id,
                    "fecha": timestamp,
                    "warnings": list(
                        validation_result.warnings
                    ),
                    "observations": list(
                        validation_result.observations
                    ),
                },
            )

            records.append(
                self._record_to_dict(record)
            )

            current_memory["historial"] = records
            current_memory["ultimo_stage_validado"] = (
                project.stage_actual
            )
            current_memory["siguiente_stage"] = (
                next_stage
            )
            current_memory["ultima_actualizacion"] = (
                timestamp
            )

            write_yaml(
                memory_path,
                current_memory,
            )

            metadata = {
                "component": self.component_name,
                "project_id": project.project_id,
                "memory_path": str(memory_path),
                "stage": project.stage_actual,
                "next_stage": next_stage,
                "records_count": len(records),
                "updated_at": timestamp,
            }

            if runtime_context is not None:
                runtime_context.memory_data = (
                    current_memory
                )

                return EngineResult.ok(
                    data=runtime_context,
                    message=(
                        "Memoria actualizada en "
                        "RuntimeContext."
                    ),
                    warnings=list(
                        validation_result.warnings
                    ),
                    metadata=metadata,
                )

            return EngineResult.ok(
                data=current_memory,
                message=(
                    "Memoria actualizada correctamente."
                ),
                warnings=list(
                    validation_result.warnings
                ),
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en MemoryEngine."
                ),
                errors=[str(error)],
                metadata={
                    "component": self.component_name,
                },
            )

    def _get_runtime_context(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> RuntimeContext | None:
        """
        Devuelve RuntimeContext cuando se utiliza
        el nuevo Runtime Framework.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input

        return None

    def _get_project(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> Project:
        """
        Obtiene Project desde cualquiera de las interfaces.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.project

        if isinstance(
            runtime_input,
            Project,
        ):
            return runtime_input

        raise TypeError(
            "MemoryEngine requiere "
            "Project o RuntimeContext."
        )

    def _get_validation_result(
        self,
        runtime_input: Project | RuntimeContext,
        validation: ValidationResult | None,
    ) -> ValidationResult | None:
        """
        Obtiene ValidationResult desde RuntimeContext
        o desde el argumento legado.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.validation_result

        return validation

    def _record_to_dict(
        self,
        record: MemoryRecord,
    ) -> dict:
        """
        Convierte MemoryRecord a una estructura YAML.
        """

        return {
            "stage": record.stage,
            "status": record.status,
            "summary": record.summary,
            "next_stage": record.next_stage,
            "metadata": dict(record.metadata),
        }

    def _get_next_stage(
        self,
        current_stage: str,
    ) -> str:
        """
        Devuelve el Stage siguiente según la secuencia oficial.
        """

        if current_stage not in STAGES:
            return FINAL_STAGE

        index = STAGES.index(
            current_stage
        )

        if index + 1 >= len(STAGES):
            return FINAL_STAGE

        return STAGES[index + 1]