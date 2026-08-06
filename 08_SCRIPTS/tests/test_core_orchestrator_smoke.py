from cips_core import CIPSOrchestrator, RetryPolicy, TaskDefinition, WorkflowStatus

def run():
    o=CIPSOrchestrator()
    o.register_agent(name="ResearchDirector",capabilities={"research"},handler=lambda p:{"findings":[f"Investigación de {p['shared_data']['topic']}"]})
    o.register_agent(name="StrategyDirector",capabilities={"strategy"},handler=lambda p:{"strategy":"Plan editorial","inputs":list(p['task_outputs'])})
    o.register_agent(name="QADirector",capabilities={"qa"},handler=lambda p:{"approved":len(p['task_outputs'])>=2})
    research=TaskDefinition("Investigación","research",task_id="research",agent_name="ResearchDirector",retry_policy=RetryPolicy(2))
    strategy=TaskDefinition("Estrategia","strategy",task_id="strategy",agent_name="StrategyDirector",dependencies={"research"})
    qa=TaskDefinition("QA","qa",task_id="qa",agent_name="QADirector",dependencies={"research","strategy"})
    w=o.create_workflow(name="Pipeline editorial mínimo",tasks=[qa,strategy,research])
    r=o.run(w,project_id="cips_core_smoke",initial_data={"topic":"Contenido profesional con IA"})
    assert r.status is WorkflowStatus.SUCCEEDED
    assert r.task_results["qa"].output["approved"] is True
    assert len(o.message_bus.history())>=8
    print("OK: Core Orchestrator operativo.")
    print(f"Workflow ID: {r.workflow_id}")
    print(f"Run ID: {r.run_id}")
    print(f"Estado: {r.status.value}")
    print(f"Tareas completadas: {len(r.task_results)}")
    print(f"Mensajes emitidos: {len(o.message_bus.history())}")
if __name__=="__main__": run()
