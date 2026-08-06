"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 063
Archivo  : production_state.py
Estado   : RELEASE
=========================================================

Gestión centralizada del estado de producción.

Responsabilidades:
- Representar el estado completo de una producción en memoria.
- Registrar el estado individual de cada Stage (PENDING → RUNNING → COMPLETED/FAILED/SKIPPED).
- Persistir snapshots JSON en disco para recuperación ante fallos.
- Restaurar estado desde el último snapshot al reiniciar un proyecto.
- Ofrecer transiciones thread-safe de estado por Stage.
- Mantener trazabilidad de versiones del schema de estado.

Este módulo NO:
- Ejecuta componentes del pipeline.
- Escribe logs de eventos (eso es production_logger.py).
- Calcula costos ni métricas de telemetría.
- Modifica archivos del proyecto fuera de su directorio de estado.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class StageStatus(str, Enum):
    """Estados posibles de una etapa de producción."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageState:
    """
    Estado individual de un Stage dentro de una producción.
    """

    stage_name: str
    status: StageStatus = StageStatus.PENDING

    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0

    result_summary: str = ""
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.stage_name = str(self.stage_name or "").strip().lower()
        if isinstance(self.status, str):
            self.status = StageStatus(self.status)
        self.started_at = str(self.started_at or "").strip()
        self.finished_at = str(self.finished_at or "").strip()
        self.duration_seconds = self._non_negative_float(self.duration_seconds)
        self.result_summary = str(self.result_summary or "").strip()
        self.error_message = str(self.error_message or "").strip()
        self.warnings = [str(w) for w in self.warnings]
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageState:
        return cls(
            stage_name=data.get("stage_name", ""),
            status=StageStatus(data.get("status", "pending")),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            duration_seconds=data.get("duration_seconds", 0.0),
            result_summary=data.get("result_summary", ""),
            error_message=data.get("error_message", ""),
            warnings=data.get("warnings", []),
            metadata=data.get("metadata", {}),
        )

    @staticmethod
    def _non_negative_float(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return round(max(number, 0.0), 6)


@dataclass
class ProductionState:
    """
    Snapshot completo del estado de una producción CIPS.

    Es la fuente de verdad en runtime. Se persiste a disco
    como respaldo de recuperación.
    """

    state_id: str
    project_id: str
    schema_version: str = "1.0"

    created_at: str = ""
    updated_at: str = ""

    current_stage: str = ""
    stages: dict[str, StageState] = field(default_factory=dict)

    global_metadata: dict[str, Any] = field(default_factory=dict)
    snapshots: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.state_id = str(self.state_id or "").strip() or str(uuid.uuid4())
        self.project_id = str(self.project_id or "").strip()
        self.schema_version = str(self.schema_version or "1.0").strip()
        self.created_at = str(self.created_at or "").strip() or self._now_iso()
        self.updated_at = str(self.updated_at or "").strip() or self._now_iso()
        self.current_stage = str(self.current_stage or "").strip().lower()

        if isinstance(self.stages, dict):
            normalized: dict[str, StageState] = {}
            for key, value in self.stages.items():
                if isinstance(value, StageState):
                    normalized[str(key).lower()] = value
                elif isinstance(value, dict):
                    normalized[str(key).lower()] = StageState.from_dict(value)
            self.stages = normalized
        else:
            self.stages = {}

        self.global_metadata = dict(self.global_metadata or {})
        self.snapshots = list(self.snapshots or [])

    def get_stage(self, stage_name: str) -> StageState:
        """Devuelve el estado de un Stage, creando uno nuevo si no existe."""
        key = str(stage_name).strip().lower()
        if key not in self.stages:
            self.stages[key] = StageState(stage_name=key)
        return self.stages[key]

    def transition_stage(
        self,
        stage_name: str,
        new_status: StageStatus,
        result_summary: str = "",
        error_message: str = "",
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StageState:
        """
        Transiciona un Stage a un nuevo estado.

        Si el estado es RUNNING, registra started_at.
        Si es terminal (COMPLETED, FAILED, SKIPPED), registra finished_at
        y calcula duration_seconds.
        """
        stage = self.get_stage(stage_name)
        now = self._now_iso()

        stage.status = new_status

        if new_status == StageStatus.RUNNING and not stage.started_at:
            stage.started_at = now

        if new_status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.SKIPPED):
            stage.finished_at = now
            if stage.started_at:
                try:
                    started_ts = time.mktime(time.strptime(stage.started_at, "%Y-%m-%dT%H:%M:%S"))
                    finished_ts = time.mktime(time.strptime(stage.finished_at, "%Y-%m-%dT%H:%M:%S"))
                    stage.duration_seconds = round(finished_ts - started_ts, 6)
                except (ValueError, OSError):
                    stage.duration_seconds = 0.0

        if result_summary:
            stage.result_summary = result_summary
        if error_message:
            stage.error_message = error_message
        if warnings:
            stage.warnings.extend([str(w) for w in warnings])
        if metadata:
            stage.metadata.update(metadata)

        self.updated_at = now
        if new_status == StageStatus.RUNNING:
            self.current_stage = stage_name

        return stage

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "project_id": self.project_id,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_stage": self.current_stage,
            "stages": {
                k: v.to_dict() for k, v in self.stages.items()
            },
            "global_metadata": self.global_metadata,
            "snapshots": self.snapshots,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProductionState:
        return cls(
            state_id=data.get("state_id", ""),
            project_id=data.get("project_id", ""),
            schema_version=data.get("schema_version", "1.0"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            current_stage=data.get("current_stage", ""),
            stages=data.get("stages", {}),
            global_metadata=data.get("global_metadata", {}),
            snapshots=data.get("snapshots", []),
        )

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


class ProductionStateManager:
    """
    Gestiona el ciclo de vida del ProductionState:
    creación, carga, transición y persistencia.
    """

    STATE_DIR_NAME = "state"
    STATE_FILE_NAME = "production_state.json"
    SCHEMA_VERSION = "1.0"

    def __init__(self, project_path: Path) -> None:
        self.project_path = Path(project_path)
        self.state_dir = self.project_path / self.STATE_DIR_NAME
        self.state_file = self.state_dir / self.STATE_FILE_NAME
        self._state: ProductionState | None = None

    # --------------------------------------------------
    # Ciclo de vida
    # --------------------------------------------------

    def load_or_create(self, project_id: str, current_stage: str = "") -> ProductionState:
        """
        Carga el estado desde disco si existe; de lo contrario,
        crea uno nuevo para el proyecto.
        """
        if self.state_file.exists():
            try:
                raw = json.loads(self.state_file.read_text(encoding="utf-8"))
                self._state = ProductionState.from_dict(raw)
                # Validar que el project_id coincida
                if self._state.project_id and self._state.project_id != project_id:
                    self._state.project_id = project_id
                    self._state.updated_at = ProductionState._now_iso()
                return self._state
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                # Estado corrupto: crear nuevo pero conservar backup
                backup_path = self.state_file.with_suffix(".json.corrupt")
                self.state_file.rename(backup_path)

        self._state = ProductionState(
            state_id=str(uuid.uuid4()),
            project_id=project_id,
            current_stage=current_stage,
        )
        self._persist()
        return self._state

    def get_state(self) -> ProductionState:
        """Devuelve el estado actual en memoria."""
        if self._state is None:
            raise RuntimeError(
                "ProductionState no inicializado. "
                "Llama a load_or_create() primero."
            )
        return self._state

    def transition_stage(
        self,
        stage_name: str,
        new_status: StageStatus,
        **kwargs: Any,
    ) -> StageState:
        """
        Transiciona un Stage y persiste inmediatamente.
        """
        state = self.get_state()
        stage = state.transition_stage(stage_name, new_status, **kwargs)
        self._persist()
        return stage

    def update_current_stage(self, stage_name: str) -> None:
        """Actualiza el Stage actual sin transicionar estado."""
        state = self.get_state()
        state.current_stage = str(stage_name).strip().lower()
        state.updated_at = ProductionState._now_iso()
        self._persist()

    def add_snapshot(self, label: str = "", metadata: dict[str, Any] | None = None) -> None:
        """
        Guarda una copia del estado actual en la lista de snapshots.
        Útil antes de operaciones críticas (finalización, exportación).

        El estado guardado NO incluye la lista de snapshots previa
        para evitar referencias circulares en la serialización JSON.
        """
        state = self.get_state()
        state_dict = state.to_dict()
        # Eliminar snapshots del estado guardado para evitar circularidad
        state_dict["snapshots"] = []
        snapshot = {
            "snapshot_id": str(uuid.uuid4()),
            "timestamp": ProductionState._now_iso(),
            "label": label,
            "state": state_dict,
            "metadata": dict(metadata or {}),
        }
        state.snapshots.append(snapshot)
        # Limitar historial a 20 snapshots para no crecer indefinidamente
        if len(state.snapshots) > 20:
            state.snapshots = state.snapshots[-20:]
        self._persist()

    def is_stage_completed(self, stage_name: str) -> bool:
        """Devuelve True si el Stage existe y está en estado COMPLETED."""
        state = self.get_state()
        stage = state.stages.get(str(stage_name).strip().lower())
        return stage is not None and stage.status == StageStatus.COMPLETED

    def get_completed_stages(self) -> list[str]:
        """Devuelve la lista de Stages completados."""
        state = self.get_state()
        return [
            name for name, stage in state.stages.items()
            if stage.status == StageStatus.COMPLETED
        ]

    # --------------------------------------------------
    # Persistencia
    # --------------------------------------------------

    def _persist(self) -> None:
        """Escribe el estado actual a disco de forma atómica."""
        if self._state is None:
            return

        self.state_dir.mkdir(parents=True, exist_ok=True)
        temp_file = self.state_file.with_suffix(".tmp")

        try:
            temp_file.write_text(
                json.dumps(self._state.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            temp_file.replace(self.state_file)
        except Exception:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            raise

    def restore_from_snapshot(self, snapshot_id: str) -> ProductionState:
        """Restaura el estado desde un snapshot específico."""
        state = self.get_state()
        for snapshot in state.snapshots:
            if snapshot.get("snapshot_id") == snapshot_id:
                restored = ProductionState.from_dict(snapshot["state"])
                restored.state_id = str(uuid.uuid4())
                restored.updated_at = ProductionState._now_iso()
                restored.snapshots = state.snapshots
                self._state = restored
                self._persist()
                return restored
        raise ValueError(f"Snapshot no encontrado: {snapshot_id}")


def get_production_state_info() -> dict[str, Any]:
    """Devuelve información pública del módulo."""
    return {
        "component": "production_state",
        "version": "0.8",
        "schema_version": ProductionStateManager.SCHEMA_VERSION,
        "models": [
            "StageStatus",
            "StageState",
            "ProductionState",
            "ProductionStateManager",
        ],
        "serializable": True,
        "state_file": "04_PROYECTOS/<PROY>/state/production_state.json",
    }
