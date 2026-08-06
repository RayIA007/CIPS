from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Mapping
import time
from .contracts import AdapterRequest, AdapterResult
from .exceptions import AdapterContractError, AdapterDisabledError, AdapterExecutionError, AdapterValidationError

class BaseAgentAdapter(ABC):
    adapter_name=''; capability=''; version='1.0.0'; enabled=True
    def __init__(self):
        self.adapter_name=self.adapter_name.strip(); self.capability=self.capability.strip()
        if not self.adapter_name: raise AdapterContractError(f'{type(self).__name__} debe declarar adapter_name.')
        if not self.capability: raise AdapterContractError(f'{type(self).__name__} debe declarar capability.')
    def __call__(self,payload:Mapping[str,Any])->AdapterResult:
        if not self.enabled: raise AdapterDisabledError(f"El adaptador '{self.adapter_name}' está deshabilitado.")
        return self.execute(AdapterRequest.from_orchestrator_payload(capability=self.capability,payload=payload))
    def execute(self,request:AdapterRequest)->AdapterResult:
        if not self.enabled: raise AdapterDisabledError(f"El adaptador '{self.adapter_name}' está deshabilitado.")
        if request.capability!=self.capability: raise AdapterValidationError(f"'{self.adapter_name}' atiende '{self.capability}', no '{request.capability}'.")
        self.validate_request(request); started=time.time()
        try:
            raw=self.run(request); result=self.normalize_result(raw_output=raw,request=request,started_at=started)
        except AdapterValidationError: raise
        except Exception as exc: raise AdapterExecutionError(f"Falló '{self.adapter_name}': {type(exc).__name__}: {exc}") from exc
        self.validate_result(result); return result
    def validate_request(self,request:AdapterRequest)->None: pass
    @abstractmethod
    def run(self,request:AdapterRequest)->Any: raise NotImplementedError
    def normalize_result(self,*,raw_output:Any,request:AdapterRequest,started_at:float)->AdapterResult:
        if isinstance(raw_output,AdapterResult): return raw_output
        return AdapterResult.success(adapter_name=self.adapter_name,capability=self.capability,output=raw_output,started_at=started_at)
    def validate_result(self,result:AdapterResult)->None:
        if result.adapter_name!=self.adapter_name: raise AdapterContractError('adapter_name inconsistente.')
        if result.capability!=self.capability: raise AdapterContractError('capability inconsistente.')
    def descriptor_metadata(self)->dict[str,Any]:
        return {'adapter':True,'adapter_name':self.adapter_name,'adapter_version':self.version,'capability':self.capability,'adapter_class':type(self).__name__}
