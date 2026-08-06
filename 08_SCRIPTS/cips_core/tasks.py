from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from .errors import CircularDependencyError, DuplicateTaskError, TaskDependencyError, WorkflowValidationError
from .utils import generate_id, utc_now_iso
class TaskStatus(str,Enum): PENDING="pending"; RUNNING="running"; SUCCEEDED="succeeded"; FAILED="failed"; SKIPPED="skipped"; RETRYING="retrying"
class WorkflowStatus(str,Enum): CREATED="created"; RUNNING="running"; SUCCEEDED="succeeded"; FAILED="failed"; PARTIAL="partial"
@dataclass(slots=True)
class RetryPolicy:
    max_attempts:int=1
    retry_exceptions:tuple[type[BaseException],...]=(Exception,)
    def __post_init__(self):
        if self.max_attempts<1: raise ValueError("max_attempts debe ser >= 1")
@dataclass(slots=True)
class TaskDefinition:
    name:str; capability:str; task_id:str=field(default_factory=lambda:generate_id("task")); agent_name:Optional[str]=None
    dependencies:set[str]=field(default_factory=set); input_data:dict[str,Any]=field(default_factory=dict); retry_policy:RetryPolicy=field(default_factory=RetryPolicy)
    continue_on_error:bool=False; metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(slots=True)
class TaskResult:
    task_id:str; status:TaskStatus; attempts:int=0; output:Any=None; error:str=""; started_at:str=""; finished_at:str=""; agent_name:str=""
    adapter_result:Any=None; metrics:dict[str,Any]=field(default_factory=dict); warnings:tuple[str,...]=(); artifacts:tuple[Any,...]=()
@dataclass(slots=True)
class WorkflowDefinition:
    name:str; tasks:list[TaskDefinition]; workflow_id:str=field(default_factory=lambda:generate_id("workflow")); version:str="1.0.0"; metadata:dict[str,Any]=field(default_factory=dict); created_at:str=field(default_factory=utc_now_iso)
class TaskGraph:
    def __init__(self,workflow):
        self.workflow=workflow; self._tasks={}
        for t in workflow.tasks:
            if t.task_id in self._tasks: raise DuplicateTaskError(t.task_id)
            self._tasks[t.task_id]=t
        self.validate()
    def validate(self):
        if not self._tasks: raise WorkflowValidationError("Workflow vacío")
        for t in self._tasks.values():
            missing=t.dependencies-set(self._tasks)
            if missing: raise TaskDependencyError(str(sorted(missing)))
            if t.task_id in t.dependencies: raise CircularDependencyError(t.task_id)
        self.topological_order()
    def topological_order(self):
        remaining={k:set(v.dependencies) for k,v in self._tasks.items()}; order=[]
        while remaining:
            ready=sorted(k for k,v in remaining.items() if not v)
            if not ready: raise CircularDependencyError("Ciclo detectado")
            order.extend(ready)
            for k in ready: del remaining[k]
            for deps in remaining.values(): deps.difference_update(ready)
        return order
    def tasks(self): return [self._tasks[k] for k in self.topological_order()]
