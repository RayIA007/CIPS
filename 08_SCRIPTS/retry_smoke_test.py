"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 059
Archivo  : retry_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral del Resilient LLM Layer.

Escenarios validados:

1. Error temporal:
   503 → 503 → éxito

2. Error permanente:
   401 → fallo inmediato

3. Agotamiento:
   503 → 503 → 503 → fallo definitivo

4. Resultado fallido mediante ProviderResult:
   429 → éxito

La prueba:
- no llama a Gemini;
- no requiere API Key;
- no realiza esperas reales;
- valida RetryPolicy;
- valida RetryEngine;
- valida metadata de intentos;
- valida backoff progresivo.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from llm_provider import ProviderResult
from retry_engine import (
    RetryEngine,
    RetryExecutionResult,
)
from retry_policy import RetryPolicy
from runtime_models import LLMResponse


@dataclass
class ScenarioResult:
    """
    Resultado de un escenario del Smoke Test.
    """

    name: str
    passed: bool
    expected_success: bool
    actual_success: bool
    attempts_count: int
    retries_count: int
    delays: list[float] = field(
        default_factory=list
    )
    errors: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class FakeClock:
    """
    Reloj determinista para evitar depender del tiempo real.
    """

    def __init__(
        self,
    ) -> None:
        self.current_time = 0.0

    def now(
        self,
    ) -> float:
        return self.current_time

    def advance(
        self,
        seconds: float,
    ) -> None:
        self.current_time += float(
            seconds
        )


class RetrySmokeTest:
    """
    Ejecuta los escenarios de validación.
    """

    TEST_NAME = "CIPS Retry Smoke Test"

    def __init__(
        self,
    ) -> None:
        self.results: list[ScenarioResult] = []

    def run(
        self,
    ) -> bool:
        """
        Ejecuta todos los escenarios.
        """

        print(self.TEST_NAME)
        print("=" * 70)
        print(
            "Esta prueba no llama a Gemini "
            "ni realiza esperas reales."
        )

        scenarios: list[
            Callable[[], ScenarioResult]
        ] = [
            self._scenario_temporary_then_success,
            self._scenario_permanent_failure,
            self._scenario_retry_exhaustion,
            self._scenario_provider_result_retry,
        ]

        for scenario in scenarios:
            result = scenario()

            self.results.append(
                result
            )

            self._print_scenario(
                result
            )

        return self._print_summary()

    # --------------------------------------------------
    # Escenarios
    # --------------------------------------------------

    def _scenario_temporary_then_success(
        self,
    ) -> ScenarioResult:
        """
        503 → 503 → éxito.
        """

        state = {
            "attempt": 0,
        }

        delays: list[float] = []

        def operation():
            state["attempt"] += 1

            if state["attempt"] < 3:
                raise Exception(
                    "503 UNAVAILABLE: "
                    "This model is currently "
                    "experiencing high demand."
                )

            return "OK"

        execution = self._execute(
            operation=operation,
            operation_name=(
                "temporary_503_then_success"
            ),
            delays=delays,
            max_attempts=3,
        )

        errors: list[str] = []

        if not execution.success:
            errors.append(
                "La operación debía terminar con éxito."
            )

        if execution.result != "OK":
            errors.append(
                "El resultado final no coincide con 'OK'."
            )

        if len(execution.attempts) != 3:
            errors.append(
                "Se esperaban exactamente 3 intentos."
            )

        if delays != [
            5.0,
            10.0,
        ]:
            errors.append(
                "Las esperas no coinciden con "
                "[5.0, 10.0]."
            )

        if not execution.metadata.get(
            "succeeded_after_retry"
        ):
            errors.append(
                "succeeded_after_retry debía ser True."
            )

        return self._build_scenario_result(
            name="503 → 503 → éxito",
            expected_success=True,
            execution=execution,
            delays=delays,
            errors=errors,
        )

    def _scenario_permanent_failure(
        self,
    ) -> ScenarioResult:
        """
        401 → fallo inmediato.
        """

        state = {
            "attempt": 0,
        }

        delays: list[float] = []

        def operation():
            state["attempt"] += 1

            raise Exception(
                "401 UNAUTHORIZED: invalid API key"
            )

        execution = self._execute(
            operation=operation,
            operation_name="permanent_401",
            delays=delays,
            max_attempts=3,
        )

        errors: list[str] = []

        if execution.success:
            errors.append(
                "La operación debía fallar."
            )

        if len(execution.attempts) != 1:
            errors.append(
                "Un error 401 no debe reintentarse."
            )

        if delays:
            errors.append(
                "No debía aplicarse ninguna espera."
            )

        if execution.metadata.get(
            "exhausted"
        ):
            errors.append(
                "Un 401 no debe marcarse como agotamiento."
            )

        first_attempt = (
            execution.attempts[0]
            if execution.attempts
            else None
        )

        if (
            first_attempt is None
            or first_attempt.status_code != 401
        ):
            errors.append(
                "No se detectó correctamente "
                "el código 401."
            )

        return self._build_scenario_result(
            name="401 → fallo inmediato",
            expected_success=False,
            execution=execution,
            delays=delays,
            errors=errors,
        )

    def _scenario_retry_exhaustion(
        self,
    ) -> ScenarioResult:
        """
        503 → 503 → 503 → agotamiento.
        """

        state = {
            "attempt": 0,
        }

        delays: list[float] = []

        def operation():
            state["attempt"] += 1

            raise Exception(
                "503 UNAVAILABLE: high demand"
            )

        execution = self._execute(
            operation=operation,
            operation_name="exhausted_503",
            delays=delays,
            max_attempts=3,
        )

        errors: list[str] = []

        if execution.success:
            errors.append(
                "La operación debía fallar "
                "después de agotar intentos."
            )

        if len(execution.attempts) != 3:
            errors.append(
                "Se esperaban exactamente 3 intentos."
            )

        if delays != [
            5.0,
            10.0,
        ]:
            errors.append(
                "Las esperas no coinciden con "
                "[5.0, 10.0]."
            )

        if not execution.metadata.get(
            "exhausted"
        ):
            errors.append(
                "exhausted debía ser True."
            )

        if execution.metadata.get(
            "retries_count"
        ) != 2:
            errors.append(
                "retries_count debía ser 2."
            )

        return self._build_scenario_result(
            name="503 → 503 → 503 → agotamiento",
            expected_success=False,
            execution=execution,
            delays=delays,
            errors=errors,
        )

    def _scenario_provider_result_retry(
        self,
    ) -> ScenarioResult:
        """
        ProviderResult 429 → éxito.
        """

        state = {
            "attempt": 0,
        }

        delays: list[float] = []

        def operation() -> ProviderResult:
            state["attempt"] += 1

            if state["attempt"] == 1:
                return ProviderResult.fail(
                    message=(
                        "Proveedor temporalmente limitado."
                    ),
                    errors=[
                        "429 TOO MANY REQUESTS"
                    ],
                    metadata={
                        "provider": "fake",
                        "status_code": 429,
                        "retryable": True,
                    },
                )

            response = LLMResponse(
                content="CIPS RETRY OK",
                model="fake-model",
                metadata={
                    "provider": "fake",
                },
            )

            return ProviderResult.ok(
                response=response,
                message=(
                    "Respuesta simulada correcta."
                ),
                metadata={
                    "provider": "fake",
                    "retryable": False,
                },
            )

        execution = self._execute(
            operation=operation,
            operation_name=(
                "provider_result_429_then_success"
            ),
            delays=delays,
            max_attempts=3,
        )

        errors: list[str] = []

        if not execution.success:
            errors.append(
                "ProviderResult debía terminar con éxito."
            )

        if len(execution.attempts) != 2:
            errors.append(
                "Se esperaban exactamente 2 intentos."
            )

        if delays != [
            5.0,
        ]:
            errors.append(
                "La espera debía ser [5.0]."
            )

        provider_result = execution.result

        if not isinstance(
            provider_result,
            ProviderResult,
        ):
            errors.append(
                "El resultado final no es ProviderResult."
            )

        elif not provider_result.success:
            errors.append(
                "ProviderResult final no fue exitoso."
            )

        retry_metadata = (
            provider_result.metadata.get(
                "retry",
                {},
            )
            if isinstance(
                provider_result,
                ProviderResult,
            )
            else {}
        )

        if retry_metadata.get(
            "attempts_count"
        ) != 2:
            errors.append(
                "La metadata enriquecida debía "
                "registrar 2 intentos."
            )

        return self._build_scenario_result(
            name="ProviderResult 429 → éxito",
            expected_success=True,
            execution=execution,
            delays=delays,
            errors=errors,
        )

    # --------------------------------------------------
    # Ejecución controlada
    # --------------------------------------------------

    def _execute(
        self,
        operation: Callable[[], Any],
        operation_name: str,
        delays: list[float],
        max_attempts: int,
    ) -> RetryExecutionResult:
        """
        Ejecuta RetryEngine sin dormir realmente.
        """

        clock = FakeClock()

        def fake_sleep(
            seconds: float,
        ) -> None:
            delays.append(
                float(seconds)
            )

            clock.advance(
                seconds
            )

        policy = RetryPolicy(
            max_attempts=max_attempts,
            initial_delay_seconds=5.0,
            backoff_multiplier=2.0,
            max_delay_seconds=30.0,
            jitter_enabled=False,
        )

        engine = RetryEngine(
            policy=policy,
            sleep_function=fake_sleep,
            clock_function=clock.now,
        )

        return engine.execute(
            operation=operation,
            operation_name=operation_name,
        )

    # --------------------------------------------------
    # Resultados
    # --------------------------------------------------

    def _build_scenario_result(
        self,
        name: str,
        expected_success: bool,
        execution: RetryExecutionResult,
        delays: list[float],
        errors: list[str],
    ) -> ScenarioResult:
        """
        Construye ScenarioResult.
        """

        return ScenarioResult(
            name=name,
            passed=not errors,
            expected_success=expected_success,
            actual_success=execution.success,
            attempts_count=len(
                execution.attempts
            ),
            retries_count=execution.metadata.get(
                "retries_count",
                0,
            ),
            delays=list(
                delays
            ),
            errors=errors,
            metadata={
                "message": execution.message,
                "exhausted": (
                    execution.metadata.get(
                        "exhausted"
                    )
                ),
                "succeeded_after_retry": (
                    execution.metadata.get(
                        "succeeded_after_retry"
                    )
                ),
                "attempts": (
                    execution.metadata.get(
                        "attempts",
                        [],
                    )
                ),
            },
        )

    def _print_scenario(
        self,
        result: ScenarioResult,
    ) -> None:
        """
        Muestra un escenario.
        """

        print()
        print("-" * 70)
        print(
            f"Escenario: {result.name}"
        )
        print("-" * 70)

        print(
            f"Resultado: "
            f"{'OK' if result.passed else 'ERROR'}"
        )

        print(
            f"Éxito esperado: "
            f"{result.expected_success}"
        )

        print(
            f"Éxito real: "
            f"{result.actual_success}"
        )

        print(
            f"Intentos: "
            f"{result.attempts_count}"
        )

        print(
            f"Reintentos: "
            f"{result.retries_count}"
        )

        print(
            f"Esperas simuladas: "
            f"{result.delays}"
        )

        print(
            f"Agotado: "
            f"{result.metadata.get('exhausted')}"
        )

        print(
            "Éxito después de reintento: "
            f"{result.metadata.get('succeeded_after_retry')}"
        )

        if result.errors:
            print("Errores:")

            for error in result.errors:
                print(
                    f"- {error}"
                )

    def _print_summary(
        self,
    ) -> bool:
        """
        Muestra el resumen final.
        """

        passed = sum(
            1
            for result in self.results
            if result.passed
        )

        failed = len(
            self.results
        ) - passed

        overall_valid = (
            failed == 0
        )

        print()
        print("=" * 70)
        print("RESUMEN RETRY")
        print("=" * 70)

        print(
            f"Escenarios ejecutados: "
            f"{len(self.results)}"
        )

        print(
            f"Escenarios aprobados: "
            f"{passed}"
        )

        print(
            f"Escenarios fallidos: "
            f"{failed}"
        )

        print(
            f"Resultado integral válido: "
            f"{overall_valid}"
        )

        if overall_valid:
            print()
            print(
                "Retry Smoke Test "
                "completado correctamente."
            )

        return overall_valid


def main() -> int:
    """
    Punto de entrada.
    """

    test = RetrySmokeTest()

    success = test.run()

    return (
        0
        if success
        else 1
    )


if __name__ == "__main__":
    sys.exit(
        main()
    )