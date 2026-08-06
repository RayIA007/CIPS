"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 063-F1
Archivo  : test_f1_smoke.py
Estado   : SMOKE TEST
=========================================================

Prueba de humo no destructiva para validar la integración
de Fase 1 (ProductionState + ProductionLogger) sin romper
el sistema existente.

EJECUCIÓN SEGURA:
- NO consume tokens de LLM.
- NO modifica proyectos reales.
- Usa un directorio temporal que se elimina al final.
- Solo verifica imports, inicialización y compatibilidad.

Uso:
    cd C:\ConsejoIA_V5\CIPS\08_SCRIPTS
    python test_f1_smoke.py
"""

from __future__ import annotations

import sys
import tempfile
import shutil
from pathlib import Path

# Asegurar que 08_SCRIPTS está en el path
scripts_dir = Path(__file__).parent.resolve()
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

# ============================================================
# COLORES PARA CONSOLA (Windows compatible)
# ============================================================
class _Colors:
    OK = "\033[92m"
    FAIL = "\033[91m"
    WARN = "\033[93m"
    INFO = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def _ok(msg: str) -> None:
    print(f"{_Colors.OK}✅ {msg}{_Colors.RESET}")


def _fail(msg: str) -> None:
    print(f"{_Colors.FAIL}❌ {msg}{_Colors.RESET}")


def _info(msg: str) -> None:
    print(f"{_Colors.INFO}ℹ️  {msg}{_Colors.RESET}")


def _warn(msg: str) -> None:
    print(f"{_Colors.WARN}⚠️  {msg}{_Colors.RESET}")


def _section(title: str) -> None:
    print()
    print(f"{_Colors.BOLD}{'=' * 60}{_Colors.RESET}")
    print(f"{_Colors.BOLD}{title}{_Colors.RESET}")
    print(f"{_Colors.BOLD}{'=' * 60}{_Colors.RESET}")


# ============================================================
# RESULTADO GLOBAL
# ============================================================
_passed = 0
_failed = 0


def _assert_true(condition: bool, label: str) -> None:
    global _passed, _failed
    if condition:
        _ok(label)
        _passed += 1
    else:
        _fail(label)
        _failed += 1


# ============================================================
# TESTS
# ============================================================
def main() -> int:
    print(f"{_Colors.BOLD}")
    print("╔" + "═" * 58 + "╗")
    print("║" + " CIPS FASE 1 — SMOKE TEST ".center(58) + "║")
    print("║" + " ProductionState + ProductionLogger ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    print(f"{_Colors.RESET}")

    temp_dir = Path(tempfile.mkdtemp(prefix="cips_f1_smoke_"))
    _info(f"Directorio temporal: {temp_dir}")

    try:
        # --------------------------------------------------
        # TEST 1: Imports
        # --------------------------------------------------
        _section("TEST 1: Imports de módulos F1")

        try:
            from production_state import (
                StageStatus,
                StageState,
                ProductionState,
                ProductionStateManager,
                get_production_state_info,
            )
            _assert_true(True, "production_state importa correctamente")
        except Exception as exc:
            _assert_true(False, f"production_state falló al importar: {exc}")
            return 1

        try:
            from production_logger import (
                LogLevel,
                LogEntry,
                StageMetrics,
                ProductionLogger,
                get_production_logger_info,
            )
            _assert_true(True, "production_logger importa correctamente")
        except Exception as exc:
            _assert_true(False, f"production_logger falló al importar: {exc}")
            return 1

        # --------------------------------------------------
        # TEST 2: ProductionStateManager (no destructivo)
        # --------------------------------------------------
        _section("TEST 2: ProductionStateManager")

        state_mgr = ProductionStateManager(temp_dir)
        state = state_mgr.load_or_create(
            project_id="SMOKE_TEST_001",
            current_stage="investigacion",
        )
        _assert_true(
            state.project_id == "SMOKE_TEST_001",
            "project_id asignado correctamente",
        )
        _assert_true(
            state.current_stage == "investigacion",
            "current_stage inicial correcto",
        )
        _assert_true(
            state.schema_version == "1.0",
            "schema_version es 1.0",
        )

        state_file = temp_dir / "state" / "production_state.json"
        _assert_true(state_file.exists(), "Archivo production_state.json creado")

        # Transición RUNNING
        stage = state_mgr.transition_stage(
            stage_name="investigacion",
            new_status=StageStatus.RUNNING,
        )
        _assert_true(
            stage.status == StageStatus.RUNNING,
            "Transición a RUNNING funciona",
        )
        _assert_true(
            stage.started_at != "",
            "started_at registrado en RUNNING",
        )

        # Transición COMPLETED
        import time
        time.sleep(0.1)
        stage = state_mgr.transition_stage(
            stage_name="investigacion",
            new_status=StageStatus.COMPLETED,
            result_summary="Smoke test OK",
            warnings=["warning de prueba"],
            metadata={"tokens": 100},
        )
        _assert_true(
            stage.status == StageStatus.COMPLETED,
            "Transición a COMPLETED funciona",
        )
        _assert_true(
            stage.finished_at != "",
            "finished_at registrado en COMPLETED",
        )
        _assert_true(
            stage.result_summary == "Smoke test OK",
            "result_summary persistido",
        )

        # Consultas
        _assert_true(
            state_mgr.is_stage_completed("investigacion"),
            "is_stage_completed devuelve True",
        )
        _assert_true(
            not state_mgr.is_stage_completed("verificacion"),
            "is_stage_completed devuelve False para stage inexistente",
        )
        _assert_true(
            state_mgr.get_completed_stages() == ["investigacion"],
            "get_completed_stages correcto",
        )

        # Snapshot
        state_mgr.add_snapshot(label="smoke_snapshot")
        _assert_true(
            len(state_mgr.get_state().snapshots) == 1,
            "Snapshot agregado sin errores",
        )

        # Recuperación desde disco
        state_mgr2 = ProductionStateManager(temp_dir)
        state2 = state_mgr2.load_or_create(project_id="SMOKE_TEST_001")
        _assert_true(
            state2.stages["investigacion"].status == StageStatus.COMPLETED,
            "Recuperación desde disco mantiene estado",
        )

        # --------------------------------------------------
        # TEST 3: ProductionLogger (no destructivo)
        # --------------------------------------------------
        _section("TEST 3: ProductionLogger")

        logger = ProductionLogger(
            project_path=temp_dir,
            legacy_logger=None,
        )

        entry_info = logger.info(
            stage="investigacion",
            message="Smoke test info",
            component="test_f1_smoke",
            tokens_in=100,
            tokens_out=50,
            cost=0.001,
        )
        _assert_true(
            entry_info.level == LogLevel.INFO,
            "LogEntry INFO creado correctamente",
        )

        entry_warn = logger.warning(
            stage="investigacion",
            message="Smoke test warning",
        )
        _assert_true(
            entry_warn.level == LogLevel.WARNING,
            "LogEntry WARNING creado correctamente",
        )

        entry_err = logger.error(
            stage="investigacion",
            message="Smoke test error",
        )
        _assert_true(
            entry_err.level == LogLevel.ERROR,
            "LogEntry ERROR creado correctamente",
        )

        log_file = temp_dir / "logs" / "production_log.jsonl"
        _assert_true(log_file.exists(), "Archivo production_log.jsonl creado")

        # Métricas
        metrics = logger.get_stage_metrics("investigacion")
        _assert_true(
            metrics.entries_count == 3,
            f"Métricas acumulan 3 entradas (actual: {metrics.entries_count})",
        )
        _assert_true(
            metrics.errors_count == 1,
            f"Métricas detectan 1 error (actual: {metrics.errors_count})",
        )
        _assert_true(
            metrics.warnings_count == 1,
            f"Métricas detectan 1 warning (actual: {metrics.warnings_count})",
        )
        _assert_true(
            metrics.total_tokens == 150,
            f"Tokens acumulados: 150 (actual: {metrics.total_tokens})",
        )

        # Rebuild desde disco
        logger2 = ProductionLogger(project_path=temp_dir, legacy_logger=None)
        logger2.rebuild_metrics()
        _assert_true(
            logger2.get_stage_metrics("investigacion").entries_count == 3,
            "Rebuild desde disco reconstruye métricas",
        )

        # --------------------------------------------------
        # TEST 4: Compatibilidad con PipelineEngine
        # --------------------------------------------------
        _section("TEST 4: Compatibilidad con PipelineEngine")

        try:
            from pipeline_engine import PipelineEngine
            _assert_true(True, "PipelineEngine importa correctamente con F1")
        except Exception as exc:
            _assert_true(False, f"PipelineEngine falló al importar: {exc}")
            return 1

        # Verificar que PipelineEngine tiene los nuevos atributos
        engine = PipelineEngine()
        _assert_true(
            hasattr(engine, "state_manager"),
            "PipelineEngine tiene atributo state_manager",
        )
        _assert_true(
            hasattr(engine, "production_logger"),
            "PipelineEngine tiene atributo production_logger",
        )
        _assert_true(
            engine.state_manager is None,
            "state_manager inicializa en None (antes de execute)",
        )
        _assert_true(
            engine.production_logger is None,
            "production_logger inicializa en None (antes de execute)",
        )

        # Verificar firma de execute (sin ejecutar)
        import inspect
        sig = inspect.signature(engine.execute)
        params = list(sig.parameters.keys())
        _assert_true(
            "project_path" in params,
            "PipelineEngine.execute() mantiene parámetro project_path",
        )

        # Verificar que _initialize_production_state existe
        _assert_true(
            hasattr(engine, "_initialize_production_state"),
            "PipelineEngine tiene método _initialize_production_state",
        )

        # --------------------------------------------------
        # TEST 5: Verificación de archivos en disco
        # --------------------------------------------------
        _section("TEST 5: Archivos generados")

        state_raw = state_file.read_text(encoding="utf-8")
        _assert_true(
            len(state_raw) > 0,
            "production_state.json no está vacío",
        )
        _assert_true(
            '"schema_version": "1.0"' in state_raw,
            "production_state.json contiene schema_version",
        )

        log_raw = log_file.read_text(encoding="utf-8")
        lines = [l for l in log_raw.strip().split("\n") if l]
        _assert_true(
            len(lines) >= 3,
            f"production_log.jsonl tiene {len(lines)} líneas",
        )

        # Verificar que cada línea es JSON válido
        all_valid = True
        for i, line in enumerate(lines):
            try:
                import json
                json.loads(line)
            except Exception:
                all_valid = False
                _warn(f"Línea {i+1} no es JSON válido")
        _assert_true(all_valid, "Todas las líneas del log son JSON válido")

    finally:
        # --------------------------------------------------
        # LIMPIEZA
        # --------------------------------------------------
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        _info(f"Directorio temporal eliminado: {temp_dir}")

    # --------------------------------------------------
    # RESUMEN
    # --------------------------------------------------
    _section("RESUMEN")
    total = _passed + _failed
    print(f"  Total assertions: {total}")
    print(f"  {_Colors.OK}Pasadas: {_passed}{_Colors.RESET}")
    print(f"  {_Colors.FAIL}Fallidas: {_failed}{_Colors.RESET}")
    print()

    if _failed == 0:
        print(f"{_Colors.OK}{_Colors.BOLD}")
        print("╔" + "═" * 58 + "╗")
        print("║" + " FASE 1 INTEGRADA CORRECTAMENTE ".center(58) + "║")
        print("║" + " TODAS LAS PRUEBAS PASARON ✅ ".center(58) + "║")
        print("╚" + "═" * 58 + "╝")
        print(f"{_Colors.RESET}")
        return 0
    else:
        print(f"{_Colors.FAIL}{_Colors.BOLD}")
        print("╔" + "═" * 58 + "╗")
        print("║" + " HAY FALLAS — REVISAR ANTES DE CONTINUAR ".center(58) + "║")
        print("╚" + "═" * 58 + "╝")
        print(f"{_Colors.RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
