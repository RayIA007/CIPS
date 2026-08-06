from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import copy
from .context import ExecutionContext
from .tasks import TaskResult, WorkflowStatus
from .utils import generate_id, utc_now_iso
@dataclass(slots=True)
class Checkpoint:
    workflow_id:str; run_id:str; status:WorkflowStatus; context:ExecutionContext; task_results:dict[str,TaskResult]
    checkpoint_id:str=field(default_factory=lambda:generate_id("checkpoint")); created_at:str=field(default_factory=utc_now_iso); metadata:dict[str,Any]=field(default_factory=dict)
class CheckpointStore(ABC):
    @abstractmethod
    def save(self,checkpoint): ...
    @abstractmethod
    def load_latest(self,workflow_id,run_id): ...
class InMemoryCheckpointStore(CheckpointStore):
    def __init__(self): self._items=[]
    def save(self,checkpoint): self._items.append(copy.deepcopy(checkpoint))
    def load_latest(self,workflow_id,run_id):
        xs=[x for x in self._items if x.workflow_id==workflow_id and x.run_id==run_id]
        return copy.deepcopy(xs[-1]) if xs else None
