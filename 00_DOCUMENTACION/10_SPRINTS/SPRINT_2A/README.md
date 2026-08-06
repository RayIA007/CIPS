# CIPS Sprint 2 — Entregable A: Adapter Framework

Añade la capa común que usarán todos los Directores para conectarse al Core Orchestrator.

## Instalación

1. Haz respaldo de `C:\ConsejoIA_V5\08_SCRIPTS`.
2. Extrae el contenido del ZIP dentro de `08_SCRIPTS`.
3. Autoriza combinar la carpeta `cips_core`.
4. Reemplaza `tests\__init__.py` si Windows lo solicita.

No elimina ni sustituye `research_prompt` ni los módulos anteriores.

## Validación

```bat
python -m tests.test_adapter_framework_smoke
```
