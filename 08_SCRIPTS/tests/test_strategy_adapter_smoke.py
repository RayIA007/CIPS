from cips_core.adapters import (
    AdapterContext,
    AdapterRequest,
    StrategyAdapterConfig,
    StrategyDirectorAdapter,
)


def main() -> None:
    adapter = StrategyDirectorAdapter(StrategyAdapterConfig(require_evidence=True))
    request = AdapterRequest(
        capability="strategy",
        context=AdapterContext(
            project_id="project_strategy_smoke",
            workflow_id="workflow_strategy_smoke",
            run_id="run_strategy_smoke",
            task_id="task_strategy_smoke",
        ),
        input_data={
            "tema": "Adopción de agentes de IA en pequeñas empresas mexicanas",
            "objetivo": "Diseñar una estrategia de adopción que genere confianza y resultados medibles",
            "research_findings": [
                "Las empresas pequeñas priorizan soluciones fáciles de implementar.",
                "La confianza aumenta cuando existen demostraciones y fuentes verificables.",
                "El costo y el tiempo de puesta en marcha son barreras principales.",
            ],
            "source_references": ["reporte_validado_001", "entrevistas_clientes_2026"],
            "audiences": [{
                "name": "Dueños de pequeñas empresas",
                "description": "Responsables de decidir inversiones tecnológicas",
                "needs": ["ahorrar tiempo", "reducir riesgo"],
            }],
        },
    )
    result = adapter.execute(request)
    assert result.succeeded
    assert result.output["package_id"].startswith("spkg_")
    assert result.metrics["evidence_count"] == 3
    assert result.metrics["score"] > 0
    print("OK: Strategy Director Adapter operativo.")
    print("Adaptador:", result.adapter_name)
    print("Capability:", result.capability)
    print("Package ID:", result.output["package_id"])
    print("Score:", result.metrics["score"])
    print("Objetivos:", result.metrics["objective_count"])
    print("Pilares:", result.metrics["pillar_count"])
    print("KPIs:", result.metrics["kpi_count"])
    print("Evidencias:", result.metrics["evidence_count"])
    print("Estado:", result.status.value)


if __name__ == "__main__":
    main()
