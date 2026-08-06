"""Exportadores multiproveedor."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from .common import safe_json_dumps
from .models import PromptPackage

class PromptExportProvider(str, Enum):
    GENERIC = "generic"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"
    DEEPSEEK = "deepseek"
    MISTRAL = "mistral"



class PromptExporter:
    @staticmethod
    def to_json(package: PromptPackage, *, indent: int = 2) -> str:
        return safe_json_dumps(package.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def to_markdown(package: PromptPackage) -> str:
        parts = ["# CIPS Research Director Prompt Package", "", "## System Prompt", "", package.system_prompt]
        if package.developer_prompt:
            parts += ["", "## Developer Prompt", "", package.developer_prompt]
        parts += ["", "## User Prompt", "", package.user_prompt, "", "## Output Contract", "", "```json",
                  safe_json_dumps(package.output_contract, indent=2, ensure_ascii=False), "```"]
        return "\n".join(parts)

    @staticmethod
    def to_messages(package: PromptPackage) -> list[dict[str, str]]:
        return package.to_messages()

    @classmethod
    def export(cls, package: PromptPackage, provider: PromptExportProvider, *, model: str = "",
               temperature: float = .2, max_tokens: Optional[int] = None) -> dict[str, Any]:
        if not isinstance(provider, PromptExportProvider):
            provider = PromptExportProvider(str(provider))
        messages = package.to_messages()
        if provider in {PromptExportProvider.OPENAI, PromptExportProvider.DEEPSEEK, PromptExportProvider.MISTRAL, PromptExportProvider.LLAMA_CPP}:
            payload: dict[str, Any] = {"model": model or "MODEL_NAME", "messages": messages, "temperature": temperature}
            if provider is PromptExportProvider.OPENAI:
                payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "cips_research_response", "strict": True, "schema": package.output_contract}}
                if max_tokens is not None: payload["max_completion_tokens"] = int(max_tokens)
            else:
                payload["response_format"] = {"type": "json_object"}
                if max_tokens is not None: payload["max_tokens"] = int(max_tokens)
            payload["metadata"] = package.metadata
            return payload
        if provider is PromptExportProvider.ANTHROPIC:
            system = package.system_prompt + ("\n\n" + package.developer_prompt if package.developer_prompt else "")
            return {"model": model or "MODEL_NAME", "system": system,
                    "messages": [{"role": "user", "content": package.user_prompt}],
                    "temperature": temperature, "max_tokens": int(max_tokens or 4096), "metadata": package.metadata}
        if provider is PromptExportProvider.GEMINI:
            system = package.system_prompt + ("\n\n" + package.developer_prompt if package.developer_prompt else "")
            config = {"temperature": temperature, "response_mime_type": "application/json", "response_schema": package.output_contract}
            if max_tokens is not None: config["max_output_tokens"] = int(max_tokens)
            return {"model": model or "MODEL_NAME", "system_instruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": package.user_prompt}]}],
                    "generation_config": config, "metadata": package.metadata}
        if provider is PromptExportProvider.OLLAMA:
            options = {"temperature": temperature}
            if max_tokens is not None: options["num_predict"] = int(max_tokens)
            return {"model": model or "MODEL_NAME", "messages": messages, "stream": False,
                    "format": package.output_contract, "options": options, "metadata": package.metadata}
        return {"messages": messages, "response_schema": package.output_contract, "metadata": package.metadata}

    @classmethod
    def to_openai(cls, package: PromptPackage, **kwargs: Any) -> dict[str, Any]:
        return cls.export(package, PromptExportProvider.OPENAI, **kwargs)

    @classmethod
    def to_anthropic(cls, package: PromptPackage, **kwargs: Any) -> dict[str, Any]:
        return cls.export(package, PromptExportProvider.ANTHROPIC, **kwargs)

    @classmethod
    def to_gemini(cls, package: PromptPackage, **kwargs: Any) -> dict[str, Any]:
        return cls.export(package, PromptExportProvider.GEMINI, **kwargs)

    @classmethod
    def to_ollama(cls, package: PromptPackage, **kwargs: Any) -> dict[str, Any]:
        return cls.export(package, PromptExportProvider.OLLAMA, **kwargs)

    @classmethod
    def to_llama_cpp(cls, package: PromptPackage, **kwargs: Any) -> dict[str, Any]:
        return cls.export(package, PromptExportProvider.LLAMA_CPP, **kwargs)

    @classmethod
    def to_deepseek(cls, package: PromptPackage, **kwargs: Any) -> dict[str, Any]:
        return cls.export(package, PromptExportProvider.DEEPSEEK, **kwargs)

    @classmethod
    def to_mistral(cls, package: PromptPackage, **kwargs: Any) -> dict[str, Any]:
        return cls.export(package, PromptExportProvider.MISTRAL, **kwargs)
