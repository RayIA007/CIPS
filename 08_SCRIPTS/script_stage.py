"""
ConsejoIA_V5
Script Stage

Genera el primer borrador del guion.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class ScriptRequest:

    topic: str

    platform: str

    duration: str

    objective: str


class ScriptStage:

    def build_script(
        self,
        request: ScriptRequest,
    ) -> str:

        return f"""# Guion

## Tema

{request.topic}

## Plataforma

{request.platform}

## Objetivo

{request.objective}

## Duración

{request.duration}

---

## Hook

Captura la atención en los primeros 3 segundos.

---

## Desarrollo

Explica el tema de forma clara, sencilla y con ejemplos.

---

## Llamado a la acción

Invita al usuario a seguir la cuenta, comentar y compartir.
"""