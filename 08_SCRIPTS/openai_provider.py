from __future__ import annotations
"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 001
Archivo  : openai_provider.py
Estado   : RELEASE
=========================================================
"""

from typing import Any
try:
    from openai import OpenAI
except Exception:
    OpenAI=None

from llm_provider import LLMProvider, ProviderResult
from runtime_models import LLMResponse

class OpenAIProvider(LLMProvider):
    provider_name="openai"
    model_name="gpt-5"
    supports_streaming=False
    supports_system_prompt=True
    supports_images=False
    supports_tools=False

    def __init__(self, api_key:str|None=None, model:str="gpt-5", temperature:float=0.2, max_tokens:int=4000, timeout:int=120):
        self.api_key=api_key
        self.model_name=model
        self.temperature=temperature
        self.max_tokens=max_tokens
        self.timeout=timeout
        self._client=None

    def configure(self, **kwargs:Any)->None:
        for k,v in kwargs.items():
            if hasattr(self,k):
                setattr(self,k,v)

    def get_client(self):
        if self._client is None:
            if OpenAI is None:
                raise RuntimeError("SDK de OpenAI no instalado.")
            self._client=OpenAI(api_key=self.api_key, timeout=self.timeout)
        return self._client

    def list_models(self)->list[str]:
        return ["gpt-5","gpt-5-mini"]

    def health_check(self)->bool:
        return OpenAI is not None

    def generate(self,prompt:str,metadata:dict[str,Any]|None=None)->ProviderResult:
        errs=self.validate_prompt(prompt)
        if errs:
            return ProviderResult.fail(message="Prompt inválido.",errors=errs,metadata=self._build_metadata(metadata))
        try:
            r=self.get_client().responses.create(model=self.model_name,input=self.prepare_prompt(prompt),max_output_tokens=self.max_tokens)
            llm=LLMResponse(content=getattr(r,"output_text",""),model=self.model_name,metadata=self._build_metadata(metadata))
            return ProviderResult.ok(response=llm,metadata=self._build_metadata(metadata))
        except Exception as e:
            return self._handle_exception(e,metadata)

    def _build_metadata(self,metadata):
        d=dict(metadata or {})
        d.update({"provider":self.provider_name,"model":self.model_name})
        return d

    def _handle_exception(self,e,metadata):
        return ProviderResult.fail(message="Error al invocar OpenAI.",errors=[str(e)],metadata=self._build_metadata(metadata))