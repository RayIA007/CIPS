"""Prueba integral del paquete refactorizado."""
from research_prompt import AdvancedResearchPromptEngine, PromptExportProvider


def run() -> None:
    engine = AdvancedResearchPromptEngine(token_budget=50_000)
    result = engine.build(
        {
            "project_id": "cips_refactor_test",
            "tema": "Validación del Research Prompt Builder refactorizado",
            "objetivo": "Comprobar construcción, diagnóstico y exportación",
            "audiencia": "Equipo CIPS",
            "plataforma": "CIPS",
            "restricciones": [
                "No inventar fuentes.",
                "Mantener trazabilidad.",
            ],
            "entregables": [
                "PromptPackage",
                "métricas",
                "diagnósticos",
            ],
        }
    )
    payload = engine.export(
        result,
        PromptExportProvider.OPENAI,
        model="MODEL_NAME",
    )

    assert result.package.system_prompt
    assert result.package.user_prompt
    assert result.package.output_contract
    assert result.score.metrics.token_estimate > 0
    assert payload["messages"]

    print("OK: refactorización operativa.")
    print(f"Package ID: {result.package.package_id}")
    print(f"Score: {result.score.overall}")
    print(f"Tokens estimados: {result.score.metrics.token_estimate}")


if __name__ == "__main__":
    run()
