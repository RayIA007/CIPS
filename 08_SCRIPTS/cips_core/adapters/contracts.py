from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional
import time, uuid


def _new_id(prefix:str)->str: return f"{prefix}_{uuid.uuid4().hex[:16]}"
def _utc_timestamp()->float: return time.time()


TASK_ARTIFACT_REF_KEY = "__cips_task_artifact_ref__"


class AdapterStatus(str,Enum):
    SUCCEEDED='succeeded'; FAILED='failed'; REJECTED='rejected'


@dataclass(frozen=True, slots=True)
class AdapterContext:
    project_id:str; workflow_id:str; run_id:str; task_id:str
    correlation_id:str=field(default_factory=lambda:_new_id('corr'))
    metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        required={'project_id':self.project_id,'workflow_id':self.workflow_id,'run_id':self.run_id,'task_id':self.task_id}
        missing=[k for k,v in required.items() if not str(v).strip()]
        if missing: raise ValueError('AdapterContext requiere: '+', '.join(sorted(missing)))
        object.__setattr__(self,'metadata',MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AdapterRequest:
    capability:str; context:AdapterContext
    input_data:Mapping[str,Any]=field(default_factory=dict)
    shared_data:Mapping[str,Any]=field(default_factory=dict)
    task_outputs:Mapping[str,Any]=field(default_factory=dict)
    request_id:str=field(default_factory=lambda:_new_id('areq'))
    created_at:float=field(default_factory=_utc_timestamp)
    task_artifacts:Mapping[str,tuple[Mapping[str,Any],...]]=field(default_factory=dict)
    def __post_init__(self):
        cap=self.capability.strip()
        if not cap: raise ValueError('AdapterRequest.capability es obligatorio.')
        object.__setattr__(self,'capability',cap)
        object.__setattr__(self,'input_data',MappingProxyType(dict(self.input_data)))
        object.__setattr__(self,'shared_data',MappingProxyType(dict(self.shared_data)))
        object.__setattr__(self,'task_outputs',MappingProxyType(dict(self.task_outputs)))
        normalized_artifacts={}
        for task_id, artifacts in dict(self.task_artifacts).items():
            normalized=[]
            for artifact in artifacts:
                if not isinstance(artifact, Mapping):
                    raise TypeError('task_artifacts solo puede contener artifacts Mapping.')
                normalized.append(MappingProxyType(dict(artifact)))
            normalized_artifacts[str(task_id)]=tuple(normalized)
        object.__setattr__(self,'task_artifacts',MappingProxyType(normalized_artifacts))
    @classmethod
    def from_orchestrator_payload(cls,*,capability:str,payload:Mapping[str,Any])->'AdapterRequest':
        try:
            context=AdapterContext(project_id=str(payload['project_id']),workflow_id=str(payload['workflow_id']),run_id=str(payload['run_id']),task_id=str(payload['task_id']),correlation_id=str(payload.get('correlation_id') or _new_id('corr')),metadata=dict(payload.get('metadata') or {}))
        except KeyError as exc:
            raise ValueError(f"Falta el campo obligatorio del Orchestrator: {exc.args[0]}") from exc
        return cls(capability=capability,context=context,input_data=dict(payload.get('input') or {}),shared_data=dict(payload.get('shared_data') or {}),task_outputs=dict(payload.get('task_outputs') or {}),task_artifacts=dict(payload.get('task_artifacts') or {}))


@dataclass(frozen=True, slots=True)
class AdapterResult:
    adapter_name:str; capability:str; status:AdapterStatus; output:Any=None; error:str=''
    warnings:tuple[str,...]=(); metrics:Mapping[str,Any]=field(default_factory=dict)
    artifacts:tuple[Mapping[str,Any],...]=(); result_id:str=field(default_factory=lambda:_new_id('ares'))
    started_at:float=field(default_factory=_utc_timestamp); finished_at:float=field(default_factory=_utc_timestamp)
    def __post_init__(self):
        an=self.adapter_name.strip(); cap=self.capability.strip()
        if not an or not cap: raise ValueError('adapter_name y capability son obligatorios.')
        if self.finished_at<self.started_at: raise ValueError('finished_at inválido.')
        if self.status is AdapterStatus.SUCCEEDED and self.error: raise ValueError('Resultado exitoso con error.')
        if self.status is not AdapterStatus.SUCCEEDED and not self.error: raise ValueError('Resultado fallido sin error.')
        object.__setattr__(self,'adapter_name',an); object.__setattr__(self,'capability',cap)
        object.__setattr__(self,'warnings',tuple(self.warnings)); object.__setattr__(self,'metrics',MappingProxyType(dict(self.metrics)))
        object.__setattr__(self,'artifacts',tuple(MappingProxyType(dict(x)) for x in self.artifacts))
    @property
    def succeeded(self)->bool: return self.status is AdapterStatus.SUCCEEDED
    @property
    def duration_ms(self)->float: return round((self.finished_at-self.started_at)*1000.0,3)
    @classmethod
    def success(cls,*,adapter_name:str,capability:str,output:Any,warnings:tuple[str,...]=(),metrics:Optional[Mapping[str,Any]]=None,artifacts:tuple[Mapping[str,Any],...]=(),started_at:Optional[float]=None):
        return cls(adapter_name=adapter_name,capability=capability,status=AdapterStatus.SUCCEEDED,output=output,warnings=warnings,metrics=dict(metrics or {}),artifacts=artifacts,started_at=started_at if started_at is not None else _utc_timestamp(),finished_at=_utc_timestamp())
    @classmethod
    def failure(cls,*,adapter_name:str,capability:str,error:str,output:Any=None,warnings:tuple[str,...]=(),metrics:Optional[Mapping[str,Any]]=None,started_at:Optional[float]=None):
        return cls(adapter_name=adapter_name,capability=capability,status=AdapterStatus.FAILED,output=output,error=error.strip() or 'Error no especificado.',warnings=warnings,metrics=dict(metrics or {}),started_at=started_at if started_at is not None else _utc_timestamp(),finished_at=_utc_timestamp())


__all__ = [
    "TASK_ARTIFACT_REF_KEY",
    "AdapterStatus",
    "AdapterContext",
    "AdapterRequest",
    "AdapterResult",
]
