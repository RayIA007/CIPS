from __future__ import annotations
from collections.abc import Iterator
from typing import Optional
from .base import BaseAgentAdapter
from .exceptions import AdapterAlreadyRegisteredError, AdapterDisabledError, AdapterNotFoundError

class AdapterRegistry:
    def __init__(self): self._by_name={}; self._by_capability={}
    def register(self,adapter:BaseAgentAdapter,*,replace:bool=False)->BaseAgentAdapter:
        en=self._by_name.get(adapter.adapter_name); ec=self._by_capability.get(adapter.capability)
        if not replace and (en is not None or ec is not None):
            collision=f"nombre '{adapter.adapter_name}'" if en is not None else f"capacidad '{adapter.capability}'"
            raise AdapterAlreadyRegisteredError(f'Ya existe un adaptador para {collision}.')
        if replace:
            if en is not None: self.unregister(en.adapter_name)
            ec=self._by_capability.get(adapter.capability)
            if ec is not None: self.unregister(ec.adapter_name)
        self._by_name[adapter.adapter_name]=adapter; self._by_capability[adapter.capability]=adapter; return adapter
    def unregister(self,adapter_name:str)->BaseAgentAdapter:
        try: adapter=self._by_name.pop(adapter_name)
        except KeyError as exc: raise AdapterNotFoundError(f"No existe '{adapter_name}'.") from exc
        self._by_capability.pop(adapter.capability,None); return adapter
    def get(self,adapter_name:str,*,enabled_only:bool=True)->BaseAgentAdapter:
        try: adapter=self._by_name[adapter_name]
        except KeyError as exc: raise AdapterNotFoundError(f"No existe '{adapter_name}'.") from exc
        if enabled_only and not adapter.enabled: raise AdapterDisabledError(f"'{adapter_name}' está deshabilitado.")
        return adapter
    def resolve(self,*,adapter_name:Optional[str]=None,capability:Optional[str]=None,enabled_only:bool=True)->BaseAgentAdapter:
        if adapter_name:
            adapter=self.get(adapter_name,enabled_only=enabled_only)
            if capability and adapter.capability!=capability: raise AdapterNotFoundError(f"'{adapter_name}' no atiende '{capability}'.")
            return adapter
        if capability:
            try: adapter=self._by_capability[capability]
            except KeyError as exc: raise AdapterNotFoundError(f"No existe adaptador para '{capability}'.") from exc
            if enabled_only and not adapter.enabled: raise AdapterDisabledError(f"El adaptador para '{capability}' está deshabilitado.")
            return adapter
        raise AdapterNotFoundError('Debe indicarse adapter_name o capability.')
    def list_adapters(self,*,enabled_only:bool=False):
        items=list(self._by_name.values())
        if enabled_only: items=[x for x in items if x.enabled]
        return sorted(items,key=lambda x:x.adapter_name)
    def __len__(self): return len(self._by_name)
    def __iter__(self)->Iterator[BaseAgentAdapter]: return iter(self.list_adapters())
