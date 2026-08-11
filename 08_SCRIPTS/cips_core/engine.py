from __future__ import annotations
from dataclasses import dataclass
from .agents import AgentRegistry
from .checkpoints import Checkpoint, CheckpointStore, InMemoryCheckpointStore
from .context import ExecutionContext
from .messages import Message, MessageBus, MessagePriority, MessageType
from .tasks import TaskGraph, TaskResult, TaskStatus, WorkflowDefinition, WorkflowStatus
from .utils import utc_now_iso
@dataclass(slots=True)
class WorkflowResult:
    workflow_id:str; run_id:str; status:WorkflowStatus; context:ExecutionContext; task_results:dict[str,TaskResult]; started_at:str; finished_at:str; error:str=""
    @property
    def succeeded(self): return self.status is WorkflowStatus.SUCCEEDED
class WorkflowEngine:
    def __init__(self,registry,*,message_bus=None,checkpoint_store=None):
        self.registry=registry
        self.message_bus=message_bus or MessageBus()
        self.checkpoint_store=checkpoint_store or InMemoryCheckpointStore()
    def run(self,workflow,*,project_id,initial_data=None,metadata=None):
        graph=TaskGraph(workflow); started=utc_now_iso()
        ctx=ExecutionContext(project_id,workflow.workflow_id,data=dict(initial_data or {}),metadata=dict(metadata or {}))
        results={}; status=WorkflowStatus.RUNNING; fatal=""
        self._pub("workflow.started",MessageType.EVENT,{"workflow_id":workflow.workflow_id,"run_id":ctx.run_id},"WorkflowEngine")
        for task in graph.tasks():
            if any(results[d].status is not TaskStatus.SUCCEEDED for d in task.dependencies):
                results[task.task_id]=TaskResult(task.task_id,TaskStatus.SKIPPED,error="Dependencia no completada",finished_at=utc_now_iso())
                self._checkpoint(workflow,status,ctx,results); continue
            result=self._execute(task,ctx); results[task.task_id]=result
            if result.status is TaskStatus.FAILED:
                ctx.set_error(task.task_id,result.error)
                if not task.continue_on_error:
                    status=WorkflowStatus.FAILED; fatal=result.error; self._checkpoint(workflow,status,ctx,results); break
            self._checkpoint(workflow,status,ctx,results)
        if status is not WorkflowStatus.FAILED:
            status=WorkflowStatus.PARTIAL if any(r.status in (TaskStatus.FAILED,TaskStatus.SKIPPED) for r in results.values()) else WorkflowStatus.SUCCEEDED
        finished=utc_now_iso(); self._checkpoint(workflow,status,ctx,results)
        self._pub("workflow.finished",MessageType.RESULT if status is WorkflowStatus.SUCCEEDED else MessageType.ERROR,{"status":status.value},"WorkflowEngine")
        return WorkflowResult(workflow.workflow_id,ctx.run_id,status,ctx,results,started,finished,fatal)
    def _execute(self,task,ctx):
        agent=self.registry.resolve(agent_name=task.agent_name,capability=task.capability)
        result=TaskResult(task.task_id,TaskStatus.RUNNING,started_at=utc_now_iso(),agent_name=agent.name)
        self._pub("task.started",MessageType.EVENT,{"task_id":task.task_id,"agent":agent.name,"capability":task.capability},"WorkflowEngine",agent.name)
        last=""
        for attempt in range(1,task.retry_policy.max_attempts+1):
            result.attempts=attempt
            try:
                raw_output=agent.handler(ctx.payload(task.task_id,task.input_data))
                if self._is_adapter_result(raw_output):
                    if not raw_output.succeeded:
                        raise RuntimeError(raw_output.error or "El adaptador devolvió un resultado fallido.")
                    result.adapter_result={
                        "result_id": raw_output.result_id,
                        "adapter_name": raw_output.adapter_name,
                        "capability": raw_output.capability,
                        "status": getattr(raw_output.status, "value", str(raw_output.status)),
                        "duration_ms": raw_output.duration_ms,
                    }
                    plain_output=self._plain(raw_output.output)
                    result.output=plain_output
                    result.metrics=self._plain(raw_output.metrics)
                    result.warnings=tuple(str(x) for x in raw_output.warnings)
                    result.artifacts=tuple(self._plain(x) for x in raw_output.artifacts)
                    ctx.set_output(task.task_id,plain_output)
                    if result.artifacts:
                        ctx.set_artifacts(task.task_id,result.artifacts)
                    self._pub(
                        "adapter.succeeded",
                        MessageType.RESULT,
                        {
                            "task_id":task.task_id,
                            "adapter":raw_output.adapter_name,
                            "result_id":raw_output.result_id,
                            "metrics":self._plain(raw_output.metrics),
                            "warnings":[str(x) for x in raw_output.warnings],
                            "artifacts":[self._plain(x) for x in raw_output.artifacts],
                        },
                        raw_output.adapter_name,
                    )
                else:
                    result.output=raw_output
                    ctx.set_output(task.task_id,raw_output)
                result.status=TaskStatus.SUCCEEDED; result.finished_at=utc_now_iso()
                self._pub("task.succeeded",MessageType.RESULT,{"task_id":task.task_id,"attempt":attempt},agent.name)
                return result
            except task.retry_policy.retry_exceptions as exc:
                last=f"{type(exc).__name__}: {exc}"
                result.status=TaskStatus.RETRYING if attempt<task.retry_policy.max_attempts else TaskStatus.FAILED
        result.error=last; result.finished_at=utc_now_iso()
        self._pub("task.failed",MessageType.ERROR,{"task_id":task.task_id,"error":last},agent.name,priority=MessagePriority.HIGH)
        return result
    @staticmethod
    def _plain(value):
        from collections.abc import Mapping
        if isinstance(value, Mapping):
            return {str(k): WorkflowEngine._plain(v) for k, v in value.items()}
        if isinstance(value, tuple):
            return tuple(WorkflowEngine._plain(v) for v in value)
        if isinstance(value, list):
            return [WorkflowEngine._plain(v) for v in value]
        if isinstance(value, set):
            return sorted(WorkflowEngine._plain(v) for v in value)
        return value
    @staticmethod
    def _is_adapter_result(value):
        return all(hasattr(value, attr) for attr in ("adapter_name","capability","status","output","metrics","artifacts","succeeded"))
    def _checkpoint(self,workflow,status,ctx,results):
        self.checkpoint_store.save(Checkpoint(workflow.workflow_id,ctx.run_id,status,ctx,dict(results)))
    def _pub(self,topic,typ,payload,source,target="",priority=MessagePriority.NORMAL):
        self.message_bus.publish(Message(topic,payload,typ,priority,source,target))
