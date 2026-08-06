from cips_core import CIPSOrchestrator, TaskDefinition
from cips_core.adapters import ResearchDirectorAdapter, StrategyDirectorAdapter


def main() -> None:
    orchestrator = CIPSOrchestrator()
    orchestrator.register_adapter(ResearchDirectorAdapter())
    orchestrator.register_adapter(StrategyDirectorAdapter())

    research = TaskDefinition(
        name="Preparar investigación",
        capability="research",
        input_data={
            "tema": "Agentes de IA para pequeñas empresas mexicanas",
            "objetivo": "Diseñar una investigación verificable sobre adopción y barreras",
        },
    )
    strategy = TaskDefinition(
        name="Construir estrategia",
        capability="strategy",
        dependencies={research.task_id},
        input_data={
            "tema": "Agentes de IA para pequeñas empresas mexicanas",
            "objetivo": "Construir una estrategia de adopción, confianza y conversión",
            # Hallazgos verificados suministrados al Strategy Director. El output del
            # Research Director actual es un PromptPackage y se conserva como trazabilidad.
            "research_findings": [
                "La facilidad de implementación es un criterio de compra prioritario.",
                "Las demostraciones concretas reducen la percepción de riesgo.",
                "La medición de ahorro de tiempo fortalece la propuesta de valor.",
            ],
            "source_references": ["research_dataset_smoke_v1"],
            "audience": "Dueños y responsables operativos de pequeñas empresas",
            "channels": ["YouTube", "TikTok", "sitio web"],
        },
    )
    workflow = orchestrator.create_workflow(
        name="Research to Strategy",
        tasks=[research, strategy],
    )
    result = orchestrator.run(workflow, project_id="project_sprint3")
    assert result.succeeded
    research_result = result.task_results[research.task_id]
    strategy_result = result.task_results[strategy.task_id]
    assert research_result.status.value == "succeeded"
    assert strategy_result.status.value == "succeeded"
    assert strategy_result.output["package_id"].startswith("spkg_")
    refs = strategy_result.output["strategy_package"]["source_references"]
    assert any(str(item).startswith("upstream_package:ppkg_") for item in refs)
    checkpoint = orchestrator.checkpoint_store.load_latest(workflow.workflow_id, result.run_id)
    assert checkpoint is not None
    print("OK: Integración Research + Strategy + Core Orchestrator operativa.")
    print("Workflow ID:", result.workflow_id)
    print("Run ID:", result.run_id)
    print("Estado:", result.status.value)
    print("Research Package:", research_result.output["package_id"])
    print("Strategy Package:", strategy_result.output["package_id"])
    print("Strategy Score:", strategy_result.metrics["score"])
    print("Evidencias:", strategy_result.metrics["evidence_count"])
    print("Referencias:", strategy_result.metrics["source_reference_count"])
    print("Mensajes emitidos:", len(orchestrator.message_bus.history()))
    print("Checkpoint: guardado")


if __name__ == "__main__":
    main()
