"""
=========================================================
Proyecto : CIPS
Release  : 0.3
Build    : 009
Archivo  : memory_engine.py
Estado   : RELEASE
=========================================================
"""

from runtime_models import EngineResult, MemoryRecord, Project, ValidationResult
from utils import write_yaml, read_yaml, current_datetime
from runtime_constants import STAGES, FINAL_STAGE

class MemoryEngine:
    """
    Registra avances del proyecto después de una validación aprobada.
    """

    def execute(
        self,
        project: Project,
        validation: ValidationResult,
    ) -> EngineResult:

        try:
            if not validation.approved:
                return EngineResult.fail(
                    message="No se puede actualizar memoria con una validación rechazada.",
                    errors=validation.errors,
                    warnings=validation.warnings,
                )

            memory_path = project.path / "memoria.yaml"
            current_memory = read_yaml(memory_path)

            if not isinstance(current_memory, dict):
                current_memory = {}

            records = current_memory.get("historial", [])

            if not isinstance(records, list):
                records = []

            next_stage = self._get_next_stage(project.stage_actual)

            record = MemoryRecord(
                stage=project.stage_actual,
                status="completed",
                summary=f"Stage {project.stage_actual} validado correctamente.",
                next_stage=next_stage,
                metadata={
                    "project_id": project.project_id,
                    "fecha": current_datetime(),
                    "warnings": validation.warnings,
                    "observations": validation.observations,
                },
            )

            records.append(
                {
                    "stage": record.stage,
                    "status": record.status,
                    "summary": record.summary,
                    "next_stage": record.next_stage,
                    "metadata": record.metadata,
                }
            )

            current_memory["historial"] = records
            current_memory["ultimo_stage_validado"] = project.stage_actual
            current_memory["siguiente_stage"] = next_stage
            current_memory["ultima_actualizacion"] = current_datetime()

            write_yaml(memory_path, current_memory)

            return EngineResult.ok(
                data=current_memory,
                message="Memoria actualizada correctamente.",
                metadata={
                    "memory_path": str(memory_path),
                    "stage": project.stage_actual,
                    "next_stage": next_stage,
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en MemoryEngine.",
                errors=[str(error)],
            )

    def _get_next_stage(self, current_stage: str) -> str:
            if current_stage not in STAGES:
                return FINAL_STAGE

            index = STAGES.index(current_stage)

            if index + 1 >= len(STAGES):
                return FINAL_STAGE

            return STAGES[index + 1]