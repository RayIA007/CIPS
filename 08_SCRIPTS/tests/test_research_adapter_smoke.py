"""Smoke test real del ResearchDirectorAdapter."""
from cips_core.adapters import (
    AdapterRegistry,
    AdapterResult,
    ResearchAdapterConfig,
    ResearchDirectorAdapter,
)


def run() -> None:
    registry = AdapterRegistry()
    adapter = registry.register(
        ResearchDirectorAdapter(
            ResearchAdapterConfig(token_budget=50_000, include_full_result=True)
        )
    )

    payload = {
        "project_id": "cips_sprint2b_test",
        "workflow_id": "workflow_research_adapter",
        "run_id": "run_research_adapter",
        "task_id": "task_build_research_prompt",
        "input": {
            "tema": "Integración del Research Director con CIPS",
            "objetivo": (
                "Construir un paquete de prompt verificable para investigar "
                "la integración modular del Research Director"
            ),
            "audiencia": "Equipo de arquitectura CIPS",
            "plataforma": "CIPS",
            "restricciones": [
                "No inventar fuentes.",
                "Mantener trazabilidad de afirmaciones y evidencia.",
            ],
            "entregables": [
                "PromptPackage",
                "métricas de calidad",
                "diagnósticos",
            ],
        },
        "shared_data": {"language": "es"},
        "task_outputs": {},
        "metadata": {"sprint": "2B"},
    }

    result = adapter(payload)

    assert isinstance(result, AdapterResult)
    assert result.succeeded
    assert result.adapter_name == "ResearchDirectorAdapter"
    assert result.capability == "research"
    assert result.output["package_id"].startswith("ppkg_")
    assert result.output["system_prompt"]
    assert result.output["user_prompt"]
    assert result.output["output_contract"]
    assert result.output["research_result"]["package"]["package_id"] == result.output["package_id"]
    assert result.metrics["token_estimate"] > 0
    assert result.metrics["score"] > 0
    assert result.artifacts[0]["artifact_type"] == "prompt_package"
    assert registry.resolve(capability="research") is adapter

    print("OK: Research Director Adapter operativo.")
    print(f"Adaptador: {result.adapter_name}")
    print(f"Capability: {result.capability}")
    print(f"Package ID: {result.output['package_id']}")
    print(f"Score: {result.metrics['score']}")
    print(f"Tokens estimados: {result.metrics['token_estimate']}")
    print(f"Diagnósticos: {result.metrics['diagnostic_count']}")
    print(f"Estado: {result.status.value}")


if __name__ == "__main__":
    run()
