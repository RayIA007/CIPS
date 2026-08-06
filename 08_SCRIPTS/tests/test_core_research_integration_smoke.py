from cips_core import (
    CIPSOrchestrator,
    ResearchAdapterConfig,
    ResearchDirectorAdapter,
    TaskDefinition,
    WorkflowStatus,
)


def run():
    orchestrator = CIPSOrchestrator()
    descriptor = orchestrator.register_adapter(
        ResearchDirectorAdapter(
            ResearchAdapterConfig(token_budget=50000, include_full_result=False)
        )
    )

    research = TaskDefinition(
        name="Investigación profesional",
        capability="research",
        task_id="research",
        input_data={
            "tema": "Uso responsable de agentes de IA en una pequeña empresa",
            "objetivo": "Construir un paquete de investigación verificable y accionable",
            "audiencia": "Propietarios de pequeñas empresas en México",
            "idioma": "es",
        },
    )
    workflow = orchestrator.create_workflow(
        name="Pipeline Research Director real",
        tasks=[research],
    )
    result = orchestrator.run(workflow, project_id="cips_sprint2c")

    task_result = result.task_results["research"]
    assert result.status is WorkflowStatus.SUCCEEDED
    assert descriptor.name == "ResearchDirectorAdapter"
    assert orchestrator.adapter_registry.resolve(capability="research")
    assert task_result.adapter_result is not None
    assert task_result.output["package_id"].startswith("ppkg_")
    assert task_result.metrics["score"] > 0
    assert result.context.task_outputs["research"]["package_id"] == task_result.output["package_id"]
    assert any(m.topic == "adapter.succeeded" for m in orchestrator.message_bus.history())
    latest = orchestrator.checkpoint_store.load_latest(workflow.workflow_id, result.run_id)
    assert latest is not None

    print("OK: Integración Research Adapter + Core Orchestrator operativa.")
    print(f"Workflow ID: {result.workflow_id}")
    print(f"Run ID: {result.run_id}")
    print(f"Estado: {result.status.value}")
    print(f"Adaptador: {task_result.adapter_result["adapter_name"]}")
    print(f"Package ID: {task_result.output['package_id']}")
    print(f"Score: {task_result.metrics['score']}")
    print(f"Tokens estimados: {task_result.metrics['token_estimate']}")
    print(f"Mensajes emitidos: {len(orchestrator.message_bus.history())}")
    print("Checkpoint: guardado")


if __name__ == "__main__":
    run()
