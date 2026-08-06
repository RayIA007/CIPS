# Instalación

1. Extraiga el contenido del ZIP en `C:\ConsejoIA_V5\08_SCRIPTS`.
2. Autorice combinar carpetas y reemplazar `content_director\__init__.py`.
3. No elimine `content_director\models.py` ni `content_director\validators.py`.
4. Ejecute:

```bat
python -m tests.test_content_planning_engine_smoke
python -m tests.test_content_planning_engine_validation
```
