import urllib.request
import json
from typing import Any
from llm_provider import LLMProvider, ProviderResult
from runtime_models import LLMResponse


class OllamaLLMProvider(LLMProvider):
    """
    Proveedor local para Ollama compatible con CIPS.
    """

    provider_name = "ollama"

    def __init__(
        self,
        model: str = "llama3:8b",
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: int = 120,
        **kwargs: Any
    ) -> None:
        self.model_name = model
        
        # Limpieza estricta de la URL base
        raw_url = str(base_url).strip().rstrip("/")
        raw_url = raw_url.replace("localhost", "127.0.0.1")
        if raw_url.endswith("/v1"):
            raw_url = raw_url[:-3].rstrip("/")
        
        self.base_url = raw_url
        self.timeout = timeout_seconds

    def generate(
        self,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """
        Envía el prompt a la API nativa de Ollama (/api/generate).
        """
        validation_errors = self.validate_prompt(prompt)
        if validation_errors:
            return ProviderResult.fail(
                message="Prompt inválido.",
                errors=validation_errors
            )

        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }

        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            
            req = urllib.request.Request(
                endpoint,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "CIPS-Engine/1.0"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    content = data.get("response", "")

                    llm_response = LLMResponse(
                        content=content,
                        model=self.model_name,
                        metadata={"provider": "ollama"}
                    )
                    return ProviderResult.ok(
                        response=llm_response,
                        message="Respuesta obtenida exitosamente desde Ollama local."
                    )
                else:
                    return ProviderResult.fail(
                        message=f"Ollama devolvió código de estado HTTP {response.status}."
                    )

        except Exception as error:
            # Imprimir el error exacto en consola para diagnóstico
            print(f"\n[DEBUG ERROR OLLAMA]: {type(error).__name__} - {str(error)}")
            return ProviderResult.fail(
                message=f"Error al comunicar con Ollama en {endpoint}.",
                errors=[str(error)]
            )