from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .utils import generate_id, utc_now_iso
@dataclass(slots=True)
class ExecutionContext:
    project_id:str; workflow_id:str; run_id:str=field(default_factory=lambda:generate_id("run")); data:dict[str,Any]=field(default_factory=dict)
    task_outputs:dict[str,Any]=field(default_factory=dict); errors:dict[str,str]=field(default_factory=dict); metadata:dict[str,Any]=field(default_factory=dict)
    created_at:str=field(default_factory=utc_now_iso); updated_at:str=field(default_factory=utc_now_iso)
    def set_output(self,task_id,value): self.task_outputs[task_id]=value; self.updated_at=utc_now_iso()
    def set_error(self,task_id,error): self.errors[task_id]=error; self.updated_at=utc_now_iso()
    def payload(self,task_id,input_data): return {"project_id":self.project_id,"workflow_id":self.workflow_id,"run_id":self.run_id,"task_id":task_id,"input":dict(input_data),"shared_data":dict(self.data),"task_outputs":dict(self.task_outputs),"metadata":dict(self.metadata)}
