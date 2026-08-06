# STD_001_LANGUAGE_CONVENTION.md

---
document:
  id: STD-001
  title: Language Convention Standard
  version: 1.0.0
  status: APPROVED
  owner: ConsejoIA_V5 Architecture
  category: Engineering Standard
---

# 1. Propósito

Este estándar establece la convención oficial de idioma utilizada en el proyecto
ConsejoIA_V5.

Su objetivo es garantizar consistencia, legibilidad, mantenibilidad y
compatibilidad con el ecosistema internacional de desarrollo de software sin
sacrificar la claridad para el equipo responsable del proyecto.

Este documento es de cumplimiento obligatorio para todos los nuevos
subsistemas, componentes, módulos y documentación generados dentro del
repositorio.

---

# 2. Filosofía

Los estándares existen para reducir la complejidad del proyecto, no para
incrementarla.

Cada estándar deberá resolver un problema real de arquitectura.

No deberán crearse estándares innecesarios ni reglas que generen burocracia.

La simplicidad, la consistencia y la mantenibilidad prevalecen sobre la
complejidad.

---

# 3. Alcance

Este estándar aplica a:

- Código fuente
- Scripts
- Bibliotecas
- Documentación
- Especificaciones
- Contratos
- Prompts
- Archivos JSON
- Archivos YAML
- Archivos Markdown
- Diagramas
- Reportes
- Mensajes al usuario

---

# 4. Convención Oficial

## 4.1 Código Fuente

Idioma oficial:

**Inglés**

Aplica a:

- nombres de archivos Python
- módulos
- paquetes
- clases
- funciones
- variables
- constantes
- enumeraciones
- interfaces
- protocolos
- modelos
- DTOs
- Schemas
- Exceptions
- Decorators

Ejemplo:

```python
class RepositoryKnowledgeGraph:
    ...
```

---

## 4.2 Comentarios

Idioma oficial:

**Español**

Ejemplo:

```python
# Validar primero los contratos antes de construir el contexto.
```

---

## 4.3 Docstrings

Idioma oficial:

**Español**

Ejemplo:

```python
class RepositoryValidator:
    """
    Valida la integridad estructural del repositorio.

    Responsabilidades:

    - Validar contratos.
    - Validar inventarios.
    - Validar manifiestos.
    """
```

---

## 4.4 Documentación

Idioma oficial:

**Español**

Aplica a:

- README
- CHANGELOG
- MANIFIESTO
- INSTALACION
- Arquitectura
- Guías
- Manuales
- Reportes
- Roadmaps

---

## 4.5 Mensajes mostrados al usuario

Idioma oficial:

**Español**

Ejemplo:

```
Proyecto validado correctamente.
```

---

## 4.6 Logs técnicos

Idioma oficial:

**Inglés**

Ejemplo:

```
Scanning repository...
```

```
Repository validation completed.
```

---

## 4.7 Archivos JSON

Las claves deberán utilizar inglés.

Ejemplo:

```json
{
    "status": "PASS",
    "repository_root": "...",
    "validation": {}
}
```

---

## 4.8 Archivos YAML

Las claves deberán utilizar inglés.

---

## 4.9 Diagramas

Idioma oficial:

**Español**

---

## 4.10 PDFs

Idioma oficial:

**Español**

---

# 5. Organización del repositorio

La documentación del proyecto deberá mantenerse dentro de:

```
00_DOCUMENTACION
```

El código fuente deberá permanecer únicamente dentro de los directorios
destinados para código.

No deberán mezclarse archivos Markdown con módulos Python salvo que el
directorio tenga como propósito específico contener documentación técnica.

---

# 6. Excepciones

Podrán utilizarse términos en inglés dentro de la documentación cuando:

- correspondan a nombres oficiales de tecnologías;
- correspondan a APIs públicas;
- correspondan a bibliotecas externas;
- correspondan a nombres propios.

Ejemplos:

- Python
- Git
- Docker
- FastAPI
- OpenAI
- Anthropic
- LangGraph

No deberán traducirse.

---

# 7. Cumplimiento

Todo nuevo componente desarrollado para ConsejoIA_V5 deberá respetar este
estándar.

Las desviaciones deberán justificarse explícitamente dentro del componente que
las requiera.

---

# 8. Historial de Cambios

| Versión | Descripción |
|----------|-------------|
| 1.0.0 | Primera versión oficial del estándar de idioma del proyecto. |