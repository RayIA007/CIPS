# Instalación — Sprint 2C

1. Haz una copia de seguridad de:

```text
C:\ConsejoIA_V5\08_SCRIPTS\cips_core
```

2. Extrae el ZIP dentro de:

```text
C:\ConsejoIA_V5\08_SCRIPTS
```

3. Autoriza combinar carpetas y reemplazar los archivos indicados.

4. No elimines los paquetes ya instalados:

```text
research_prompt\
cips_core\adapters\
```

5. Ejecuta:

```bat
python -m tests.test_core_research_integration_smoke
```

## Validación acumulativa recomendada

```bat
python -m tests.test_core_orchestrator_smoke
python -m tests.test_adapter_framework_smoke
python -m tests.test_research_adapter_smoke
python -m tests.test_core_research_integration_smoke
```
