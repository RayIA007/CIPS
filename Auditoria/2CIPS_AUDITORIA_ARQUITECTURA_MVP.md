# TAREA: AUDITORÍA ARQUITECTÓNICA DEL MVP DE CIPS

## Resumen Ejecutivo

Este documento presenta una auditoría arquitectónica del MVP de CIPS, basada en el análisis estático del código fuente y la documentación disponible en el repositorio `C:\ConsejoIA_V5`. El objetivo es determinar la arquitectura documentada versus la implementada, identificar brechas, y proponer un camino mínimo para la finalización del MVP, priorizando la producción de contenido confiable y monetizable.

## 1. Documentación Raíz

Se revisaron los siguientes archivos de documentación raíz:

- [x] Instrucciones.md
- [x] PROJECT_MANIFEST.yaml
- [x] ESTRUCTURA_PROYECTO.txt
- [x] ARBOL_CIPS.txt
- [x] ARBOL_COMPLETO_CIPS.txt
- [x] ConsejoIA_v5_TREE.txt
- [x] INVENTARIO_PROYECTO.csv
- [x] project_folders_inventory.csv
- [x] project_tree.txt
- [x] duplicate_file_names.txt

Estos archivos fueron utilizados para comprender la estructura general del proyecto y la intención de la organización de los archivos. Los archivos `ARBOL_CIPS.txt`, `ARBOL_COMPLETO_CIPS.txt`, `ConsejoIA_v5_TREE.txt` y `project_tree.txt` son particularmente útiles para obtener una vista rápida del árbol de directorios. El `PROJECT_MANIFEST.yaml` proporciona metadatos del framework y la versión actual (`0.1.0`, `BUILD_001`, `DEVELOPMENT`). El `duplicate_file_names.txt` indica la presencia de archivos duplicados, incluyendo `research_director_prompt_builder.py` y varios archivos de telemetría y proyectos generados, lo cual es una señal de posibles inconsistencias o historiales de refactorización.

## 2. Arquitectura y Estándares Documentados

Se revisó la siguiente documentación de arquitectura y estándares:

- [x] 00_DOCUMENTACION/CIPS_CORE_CONSTITUTION.md
- [x] 00_DOCUMENTACION/CIPS_ARCHITECTURE_STANDARD.md
- [x] 00_DOCUMENTACION/CIPS_ENGINEERING_STANDARD.md
- [ ] 00_DOCUMENTACION/CIPS_RUNTIME_ARCHITECTURE.md
- [ ] 00_DOCUMENTACION/CIPS_LAYERED_RUNTIME_ARCHITECTURE.md
- [ ] 00_DOCUMENTACION/architecture/CIPS_PRODUCTION_ARCHITECTURE_V1.md
- [ ] 00_DOCUMENTACION/specifications
- [x] 08_SCRIPTS/ARQUITECTURA.md
- [x] 08_SCRIPTS/ESTRUCTURA.md
- [x] 08_SCRIPTS/README.md
- [x] 08_SCRIPTS/MANIFIESTO.md
- [x] 08_SCRIPTS/CHANGELOG.md

### CIPS_CORE_CONSTITUTION.md
Este documento establece los principios permanentes que gobiernan CIPS, priorizando la credibilidad, honestidad intelectual, utilidad, claridad y responsabilidad. Define una jerarquía de autoridad donde la Constitución es la máxima autoridad, seguida por estándares de lenguaje, arquitectura, ingeniería, el CIPS Intelligence Framework (CIF), Expert Council, Knowledge Engine, Pipeline Engine, Prompt Assembly Engine y finalmente el Software. Prohíbe la producción de contenido para desinformación, manipulación o sensacionalismo.

### CIPS_ARCHITECTURE_STANDARD.md
Define la arquitectura oficial de CIPS con principios de modularidad, separación de responsabilidades (conocimiento fuera del código), reutilización, escalabilidad, independencia tecnológica, bajo acoplamiento y alta cohesión. Establece ocho capas arquitectónicas (Usuario, CIPS Core Constitution, CIPS Standards, CIPS Intelligence Framework, Knowledge Engine, Pipeline Engine, Application Layer, Infrastructure Layer), donde cada capa depende únicamente de la superior. También describe la estructura de directorios oficial del proyecto y las responsabilidades de cada uno (00_DOCUMENTACION, 01_CONFIG, 02_PROMPTS, 03_PLANTILLAS, 04_PROYECTOS, 05_OUTPUTS, 06_MEMORIA, 07_LOGS, 08_SCRIPTS, 09_KNOWLEDGE, CIPS). Detalla las responsabilidades de los motores de software (Project Manager, Pipeline Engine, Knowledge Engine, Prompt Assembly Engine, Export Engine) y el flujo oficial del software.

### CIPS_ENGINEERING_STANDARD.md
Establece la metodología oficial para el diseño, desarrollo, documentación, validación y evolución de CIPS. Se basa en una filosofía de evolución incremental. Principios clave incluyen que la arquitectura gobierna el código, el conocimiento gobierna la IA, el código debe ser simple, modularidad, reutilización, escalabilidad e independencia. Define un flujo de desarrollo con fases obligatorias (Idea, Análisis, Arquitectura, Diseño, Implementación, Validación, Documentación, Integración, Release). Describe estados de release (Draft, Review, Release Candidate, Release, Deprecated), principios de trazabilidad, responsabilidad única para archivos y funciones, y estándares de documentación y legibilidad del código. Además, detalla estándares para Knowledge Modules, Prompts, Configuración, Logs y Proyectos, así como convenciones de nombrado (snake_case para archivos/funciones/variables, PascalCase para clases y MAYUSCULAS para constantes). Prohíbe expresamente dependencias circulares y enfatiza la mantenibilidad.

### 08_SCRIPTS/ARQUITECTURA.md
Documenta el `CIPS Core Orchestrator` como una implementación inicial para registro de agentes, resolución por capacidades, DAG de tareas, validación de dependencias, detección de ciclos, reintentos, contexto compartido, bus de mensajes, checkpoints y resultado integral de workflow. Menciona que el siguiente sprint integrará el `Research Director` refactorizado como primer agente real.

### 08_SCRIPTS/ESTRUCTURA.md
Presenta una estructura refactorizada dentro de `08_SCRIPTS`, con un directorio `research_prompt` que contiene varios módulos (`common.py`, `models.py`, `templates.py`, `contracts.py`, `builder.py`, etc.) y un directorio `tests` con `test_refactor_smoke.py`.

### 08_SCRIPTS/README.md
Documenta el `CIPS Sprint 2 — Entregable A: Adapter Framework`, que añade una capa común para que los Directores se conecten al `Core Orchestrator`. Incluye instrucciones de instalación y un comando de validación para `tests.test_adapter_framework_smoke`.

### 08_SCRIPTS/MANIFIESTO.md
Lista los archivos incluidos en el `Manifiesto Versión: 2A.1.0.0`, que corresponden principalmente a componentes del `Adapter Framework` (`cips_core/adapters/` y un test relacionado).

### 08_SCRIPTS/CHANGELOG.md
Detalla los añadidos del `CHANGELOG — Sprint 2A 1.0.0`, que incluyen `BaseAgentAdapter`, `AdapterContext`, `AdapterRegistry`, etc. Indica que no se modifican `engine.py`, `agents.py` ni `research_prompt/`, y que la conexión con `AgentRegistry` se realizará en el Entregable C.

### Hallazgos Generales de Arquitectura Documentada:
Existe una documentación exhaustiva y detallada de la arquitectura de CIPS, con un fuerte énfasis en la modularidad, separación de responsabilidades y la reutilización. Se definen claramente capas, motores y un flujo de ejecución. La documentación también aborda aspectos de calidad del código, estándares de documentación y gestión de cambios. Se observa una evolución documentada a través de los Sprints, lo que sugiere un desarrollo iterativo.

## 3. Configuración

Se revisó la siguiente configuración:

- [x] 01_CONFIG/config_global.yaml
- [x] 01_CONFIG/knowledge_rules.yaml
- [x] 01_CONFIG/llm.yaml
- [x] 01_CONFIG/pipeline.yaml
- [x] 01_CONFIG/provider_pricing.yaml
- [x] 01_CONFIG/validation_rules.yaml

### 01_CONFIG/config_global.yaml
Define la configuración general del framework CIPS, incluyendo la versión (`0.1.0`), idioma (`es`), codificación (`utf-8`), zona horaria (`America/Mexico_City`), y opciones para guardar logs, historial y autosave. También especifica las rutas de los directorios clave del proyecto, lo cual es consistente con el `CIPS_ARCHITECTURE_STANDARD.md`.

### 01_CONFIG/knowledge_rules.yaml
Define reglas para la selección de módulos de conocimiento por cada etapa del pipeline. Por ejemplo, para `investigacion`, se requieren los módulos `KM-000` a `KM-008`. Esto es consistente con el principio de especialización y ensamblaje de prompts, donde el conocimiento se carga dinámicamente según la etapa.

### 01_CONFIG/llm.yaml
Configura los proveedores de LLM. Indica que el runtime está en modo `automatic` con `gemini` como proveedor (`gemini-3.5-flash`), y que está `enabled: true`. Sin embargo, un comentario indica: 

## Arquitectura Oficial
### CIPS RUNTIME ARCHITECTURE (Documento: CIPS_RUNTIME_ARCHITECTURE.md)

La arquitectura operativa de CIPS se centra en un flujo de ejecución lineal coordinado por un `Pipeline Engine`. Se compone de varios "Engines" especializados, cada uno con una única responsabilidad. La comunicación entre estos motores se realiza exclusivamente a través de objetos de datos definidos, garantizando un bajo acoplamiento. El ciclo de vida de un proyecto está estrictamente definido con estados y transiciones claras, y el sistema está diseñado para la recuperación de errores sin pérdida de información, manteniendo el estado del proyecto consistente.

**Componentes del Runtime:**
*   **Project Manager:** Crea y administra la estructura física del proyecto, incluyendo carpetas y archivos base, y mantiene `proyecto.yaml` y `memoria.yaml`.
*   **Knowledge Engine:** Carga y selecciona módulos de conocimiento relevantes, resuelve dependencias y los entrega estructurados al Context Engine.
*   **Context Engine:** Recibe módulos de conocimiento, los ordena, elimina redundancias y prepara un `Context Object`.
*   **Prompt Builder:** Recibe el `Context Object` y el objetivo del Stage, construye el `Prompt Object` y renderiza el prompt final en Markdown.
*   **Validator Engine:** Verifica la estructura, formato y consistencia de los resultados, aprobándolos o rechazándolos.
*   **Memory Engine:** Registra avances, guarda decisiones, actualiza la memoria del proyecto y registra los próximos pasos.
*   **Pipeline Engine:** Coordinador principal, lee el estado del proyecto, determina el Stage actual, invoca al motor correspondiente, actualiza el estado y detiene el flujo si es necesario.

**Flujo General del Runtime:**
`Usuario → run.py → Pipeline Engine → Project Manager → Knowledge Engine → Context Engine → Prompt Builder → Modelo IA → Validator Engine → Memory Engine → Pipeline Engine → Siguiente Stage`

**Estados del Proyecto:**
`CREATED → READY → RUNNING → WAITING_RESPONSE → VALIDATING → COMPLETED → ARCHIVED` (con transiciones a `ERROR` desde `RUNNING` y de `ERROR` a `READY` para reanudar).

**Objetos de Intercambio:**
`Project → KnowledgeResult → ContextResult → PromptResult → LLMResponse → ValidationResult → MemoryResult`

### CIPS LAYERED RUNTIME ARCHITECTURE (Documento: CIPS_LAYERED_RUNTIME_ARCHITECTURE.md)

Esta arquitectura introduce un modelo de capas para el Runtime, buscando una mayor modularidad y extensibilidad. Cada capa tiene una responsabilidad única y solo se comunica con la capa inmediatamente siguiente a través de objetos definidos. Esto permite la integración de nuevos componentes sin alterar el flujo principal.

**Capas Oficiales y Componentes Actuales (o esperados):**
*   **CAPA 1: Project Layer:** `ProjectManager` (administra el proyecto activo).
*   **CAPA 2: Knowledge Layer:** (Carga de conocimiento).
*   **CAPA 3: Resolution Layer:** (Reducción de módulos de conocimiento).
*   **CAPA 4: Compression Layer:** (Modificación de contenido de módulos).
*   **CAPA 5: Context Layer:** (Organiza información).
*   **CAPA 6: Prompt Layer:** (Construye el prompt operativo).
*   **CAPA 7: LLM Layer:** (Interactúa con el proveedor de IA).
*   **CAPA 8: Validation Layer:** (Determina si la respuesta es aceptada o rechazada).
*   **CAPA 9: Memory Layer:** (Registra el avance del proyecto).
*   **CAPA 10: Learning Layer:** (Analiza patrones para mejorar futuras ejecuciones).

**Contratos entre Capas (Flujo de Objetos):**
`Project → KnowledgeModule[] → KnowledgeModule[] (Resolution) → KnowledgeModule[] (Compression) → ContextObject → PromptObject → LLMResponse → ValidationResult → MemoryRecord → Learning Events`

### CIPS PRODUCTION ARCHITECTURE V1.0 (Documento: CIPS_PRODUCTION_ARCHITECTURE_V1.md)

Esta arquitectura define CIPS como un "Estudio Profesional de Producción de Contenido impulsado por Inteligencia Artificial", replicando la organización de una empresa de producción de contenido con roles especializados. El objetivo es producir contenido de calidad profesional, verificable, escalable y monetizable con mínima intervención humana. El `Master Producer` es el coordinador central que dirige la producción, y cada "Director" o "Especialista" tiene responsabilidades definidas y entrega productos concretos.

**Organigrama (Direcciones):**
`Master Producer` coordina:
*   Director de Investigación
*   Director Estratégico
*   Director Creativo
*   Director de Guion
*   Director de Arte IA
*   Director SEO
*   Director de Plataforma
*   Director de Monetización
*   Director de Calidad

**Flujo General de Producción:**
`Solicitud del Usuario → Master Producer → Director de Investigación → Director Estratégico → Director Creativo → Director de Guion → Director de Arte IA → Director SEO → Director de Plataforma → Director de Monetización → Director de Calidad → Proyecto Final`

**Entregables Mínimos del Proyecto Final:**
`README.md, 01_Brief.md, 02_Investigacion.md, 03_Estrategia.md, 04_Concepto_Creativo.md, 05_Guion.md, 06_Storyboard.md, 07_Prompts_Imagen.md, 08_Prompts_Video.md, 09_Audio.md, 10_SEO.md, 11_Publicacion.md, 12_Monetizacion.md, 13_QA.md, 14_Checklist.md`

**Fases de Implementación (Roadmap):**
1.  **FASE 1: Infraestructura Base** (Finalizada): Runtime Architecture, Telemetry, Runtime Health, Cost Analytics, Runtime Optimizer, Project Intelligence, Executive Dashboard, Intelligence Pipeline.
2.  **FASE 2: Producción** (En desarrollo): Master Producer, Director de Investigación, Director Estratégico, Director Creativo, Director de Guion, Director de Arte IA, Director SEO, Director de Plataforma, Director de Monetización, Director de Calidad.

## Runtime Oficial

El runtime oficial de CIPS, según los documentos, se caracteriza por un flujo de ejecución estricto y una clara separación de responsabilidades a través de "Engines" y "Capas". El `Pipeline Engine` es el orquestador principal, que guía el proyecto a través de una secuencia de etapas predefinidas. La comunicación entre los componentes se realiza a través de objetos de datos estandarizados, lo que promueve la modularidad y la mantenibilidad. La arquitectura también incorpora un sólido manejo de errores, asegurando que el estado del proyecto se mantenga íntegro incluso en caso de fallos, y permite la reanudación desde el último punto validado.

El flujo de ejecución en alto nivel es:

1.  **Inicio:** El usuario inicia un proyecto a través de `run.py`, que invoca al `Pipeline Engine`.
2.  **Coordinación del Pipeline:** El `Pipeline Engine` lee el estado del proyecto (`proyecto.yaml`), identifica el "Stage" actual y coordina la ejecución de los "Engines" especializados.
3.  **Procesamiento por Engines:** Los "Engines" (Project Manager, Knowledge Engine, Context Engine, Prompt Builder, LLM, Validator Engine, Memory Engine) procesan la información de manera secuencial, intercambiando "EngineResults" y objetos de datos específicos de cada capa.
4.  **Interacción con LLM:** El `Prompt Builder` genera un prompt que es enviado a un Modelo IA (LLM).
5.  **Validación:** La respuesta del LLM es validada por el `Validator Engine`.
6.  **Actualización de Memoria:** Si la validación es exitosa, el `Memory Engine` actualiza el estado del proyecto y la memoria.
7.  **Transición de Stage:** El `Pipeline Engine` determina el siguiente Stage y actualiza `proyecto.yaml`.
8.  **Finalización o Continuación:** El proceso se repite hasta que todos los Stages se completan, momento en el cual el proyecto se marca como finalizado y se generan los outputs finales.
9.  **Manejo de Errores:** En caso de error, el Runtime registra el incidente, detiene el proceso afectado, conserva la información válida y permite la reanudación.

Las capas, aunque conceptuales en `CIPS_RUNTIME_ARCHITECTURE.md`, son formalizadas en `CIPS_LAYERED_RUNTIME_ARCHITECTURE.md`, introduciendo capas como `Resolution Layer`, `Compression Layer`, y `Learning Layer`, cada una con sus propios contratos de entrada y salida, lo que indica una evolución hacia una mayor granularidad y especialización en el manejo del conocimiento y el contexto antes de llegar al LLM.

La `CIPS_PRODUCTION_ARCHITECTURE_V1.0.md` complementa esto al definir un flujo de producción de contenido de alto nivel, con el `Master Producer` orquestando una serie de "Directores" especializados (Investigación, Estratégico, Creativo, etc.), que se alinean con los "Engines" del Runtime, pero a un nivel más conceptual y de negocio.

## Comparación Documentación vs Código

### Arquitectura Oficial vs. Directorio `08_SCRIPTS/`

La documentación describe una arquitectura modular basada en "Engines" y "Capas", con un `Pipeline Engine` central. El directorio `08_SCRIPTS/` contiene varios archivos que sugieren la implementación de muchos de estos componentes.

**Componentes Existentes (confirmados por nombres de archivo en `08_SCRIPTS/`):**

*   **Pipeline Engine:** `pipeline_engine.py`, `pipeline_runner.py`, `content_pipeline.py`, `intelligence_pipeline.py` (sugiere múltiples tipos de pipelines o su evolución).
*   **Project Manager:** `project_manager.py`.
*   **Knowledge Engine:** `knowledge_engine.py`, `knowledge_resolver.py`, `knowledge_injector.py`, `knowledge_module_builder.py`.
*   **Context Engine:** `context_engine.py`, `context_compressor.py` (relacionado con la Compression Layer).
*   **Prompt Builder:** `prompt_builder.py`, `prompt_engine.py`, `prompt_renderer.py`, `master_producer_prompt_builder.py`, `research_director_prompt_builder.py` (sugiere builders especializados para roles).
*   **Validator Engine:** `validator_engine.py`.
*   **Memory Engine:** `memory_engine.py`.
*   **LLM Layer/Providers:** `llm_adapter.py`, `llm_manager.py`, `llm_provider.py`, `llm_provider_factory.py`, `gemini_llm_provider.py`, `openai_provider.py`, `manual_llm_provider.py`, `mock_provider.py` (indica soporte para múltiples LLMs y adaptadores).
*   **Core Orchestrator:** `core_orchestrator.py` (podría ser el `Pipeline Engine` o un componente relacionado de más alto nivel).
*   **Logging:** `logger.py` (confirma la capacidad de registro de errores).
*   **Runtime Models:** `runtime_models.py`, `runtime_context.py`, `runtime_component.py`, `runtime_constants.py` (sugiere la implementación de los objetos de intercambio y la estructura del runtime).
*   **Master Producer:** `master_producer.py`, `master_producer_models.py`, `master_producer_prompt_builder.py` (confirma la existencia del orquestador de alto nivel).
*   **Research Director:** `research_director_models.py`, `research_director_prompt_builder.py` (confirma la existencia de un director de investigación).

**Componentes Faltantes (según nombres de archivo explícitos):**

*   **Learning Layer/Engine:** No se encuentra un archivo `learning_engine.py` o similar.
*   **Director Estratégico, Creativo, de Guion, de Arte IA, SEO, de Plataforma, de Monetización, de Calidad:** Si bien `research_director` y `master_producer` existen, no hay archivos explícitos para los otros roles de "Director" mencionados en `CIPS_PRODUCTION_ARCHITECTURE_V1.0.md`.

**Componentes Parcialmente Implementados o Reemplazados:**

*   **Resolution Layer & Compression Layer:** Los documentos las mencionan como capas separadas. En el código, `knowledge_resolver.py` podría manejar la "Resolution" y `context_compressor.py` la "Compression" o parte de ella, pero no hay una clara delimitación de estos como capas explícitas con sus propios engines independientes como se describe en `CIPS_LAYERED_RUNTIME_ARCHITECTURE.md`.
*   **`run.py`:** En la documentación (`CIPS_RUNTIME_ARCHITECTURE.md`), `run.py` es el punto de entrada que llama al `Pipeline Engine`. El archivo `CIPS/run.py` existe, lo que confirma su rol como punto de entrada. Sin embargo, su implementación real deberá ser analizada para verificar si cumple estrictamente con las responsabilidades descritas (iniciar, mostrar menú, recibir opción, llamar al `Pipeline Engine`, sin lógica de negocio).
*   **Objetos de Intercambio:** Existen `runtime_models.py` y archivos de `models.py` en subdirectorios como `content_director/` y `knowledge_assets/`, lo que sugiere la implementación de modelos de datos para la comunicación entre componentes, alineado con el principio de intercambio de objetos. Sin embargo, la exactitud de los nombres y estructuras (`KnowledgeResult`, `ContextResult`, etc.) requeriría una inspección más profunda del contenido de esos archivos.

## Hallazgos

1.  **Coherencia Documental:** Los tres documentos analizados (`CIPS_RUNTIME_ARCHITECTURE.md`, `CIPS_LAYERED_RUNTIME_ARCHITECTURE.md`, `CIPS_PRODUCTION_ARCHITECTURE_V1.md`) presentan una visión coherente de la arquitectura, evolucionando desde un nivel de ejecución (`Runtime`) hacia un modelo de capas más granular (`Layered Runtime`) y finalmente a una estructura organizacional de producción de contenido (`Production Architecture`). Los principios de modularidad, responsabilidad única y comunicación basada en contratos son consistentes en todos los documentos.
2.  **"Engines" vs. "Capas" vs. "Directores":** Se observa una correspondencia conceptual entre los "Engines" del Runtime, las "Capas" del Runtime en capas, y los "Directores" de la Arquitectura de Producción. Por ejemplo, `Knowledge Engine` se alinea con `Knowledge Layer` y el concepto de `Director de Investigación`.
3.  **Avance de la Implementación:** La Fase 1 del Roadmap (`Infraestructura Base`) en `CIPS_PRODUCTION_ARCHITECTURE_V1.0.md` menciona componentes como `Runtime Architecture`, `Telemetry`, `Runtime Health`, `Cost Analytics`, `Runtime Optimizer`, `Project Intelligence`, `Executive Dashboard`, `Intelligence Pipeline`. Muchos de estos tienen archivos correspondientes en `08_SCRIPTS/` (e.g., `telemetry_engine.py`, `runtime_health_monitor.py`, `cost_analyzer.py`, `runtime_optimizer.py`, `project_intelligence_engine.py`, `dashboard_generator.py`, `intelligence_pipeline.py`), lo que sugiere un progreso significativo en la implementación de la infraestructura base.
4.  **Fase de Producción en Curso:** La Fase 2 (`Producción`) está "En desarrollo" y prioriza el `Master Producer` y el `Director de Investigación`. Los archivos `master_producer.py` y `research_director.py` confirman que estos componentes clave están siendo implementados.
5.  **Brechas en la Implementación de Roles:** Si bien los documentos describen un extenso "organigrama" de directores, la mayoría de estos roles (Director Estratégico, Creativo, de Guion, etc.) no tienen una contraparte de archivo explícita en `08_SCRIPTS/`, lo que sugiere que su implementación aún está en fases tempranas o se gestionan de forma más abstracta dentro de los pipelines existentes, o mediante la lógica de `master_producer` y `research_director`.
6.  **Objetos de Intercambio:** La presencia de `runtime_models.py` y otros archivos `models.py` en subdirectorios es un buen indicio de que se están definiendo los contratos de comunicación entre componentes, lo cual es un principio clave de la arquitectura documentada.
7.  **`run.py`:** Se confirma la existencia de `CIPS/run.py` como el punto de entrada, alineado con la documentación. Su rol como un simple iniciador sin lógica de negocio es un principio importante a verificar en su contenido.

## Evidencias

*   **`00_DOCUMENTACION/CIPS_RUNTIME_ARCHITECTURE.md`:** Define los 7 Engines principales (Project Manager, Knowledge, Context, Prompt Builder, Validator, Memory, Pipeline), su flujo secuencial, estados del proyecto (`CREATED`, `READY`, `RUNNING`, `VALIDATING`, `COMPLETED`, `ERROR`, `ARCHIVED`), y el intercambio de objetos (`Project`, `KnowledgeResult`, `ContextResult`, `PromptResult`, `LLMResponse`, `ValidationResult`, `MemoryResult`). Enfatiza la responsabilidad única y la comunicación por entradas y salidas explícitas.

*   **`00_DOCUMENTACION/CIPS_LAYERED_RUNTIME_ARCHITECTURE.md`:** Formaliza las 10 capas del Runtime (`Project`, `Knowledge`, `Resolution`, `Compression`, `Context`, `Prompt`, `LLM`, `Validation`, `Memory`, `Learning`), sus responsabilidades y los contratos de entrada/salida entre ellas. Menciona `ProjectManager` como el componente actual de la `Project Layer` y `Context Compressor` como un componente potencial para la `Compression Layer`.

*   **`00_DOCUMENTACION/architecture/CIPS_PRODUCTION_ARCHITECTURE_V1.md`:** Describe CIPS como un estudio de producción de contenido con un `Master Producer` y varios "Directores" especializados. Define un flujo de producción lineal, entregables mínimos para un proyecto final, y un roadmap de implementación con Fases 1 (Infraestructura Base) y 2 (Producción) siendo las más relevantes para la auditoría actual. La Fase 1 se declara como "Finalizada" e incluye `Runtime Architecture`, `Telemetry`, `Runtime Health`, `Cost Analytics`, `Runtime Optimizer`, `Project Intelligence`, `Executive Dashboard`, `Intelligence Pipeline`. La Fase 2 está "En desarrollo" y prioriza `Master Producer` y `Director de Investigación`.

*   **Directorio `08_SCRIPTS/` (listado de archivos):**
    *   **Engines principales:** Presencia de `project_manager.py`, `knowledge_engine.py`, `context_engine.py`, `prompt_builder.py`, `validator_engine.py`, `memory_engine.py`, `pipeline_engine.py`, `pipeline_runner.py`.
    *   **Componentes de capas:** `knowledge_resolver.py` (para Resolution Layer), `context_compressor.py` (para Compression Layer).
    *   **LLM Integration:** `llm_adapter.py`, `llm_manager.py`, `llm_provider_factory.py`, `gemini_llm_provider.py`, `openai_provider.py`, `mock_provider.py`.
    *   **Orquestación de alto nivel:** `core_orchestrator.py`, `master_producer.py`.
    *   **Directores específicos:** `research_director.py`.
    *   **Infraestructura Base (Fase 1):** `telemetry_engine.py`, `runtime_health_monitor.py`, `cost_analyzer.py`, `runtime_optimizer.py`, `project_intelligence_engine.py`, `dashboard_generator.py`, `intelligence_pipeline.py`.
    *   **Modelos de datos:** `runtime_models.py`, `master_producer_models.py`, `research_director_models.py`, y subdirectorios `cips_core/` y `knowledge_assets/` con sus propios archivos `models.py`.
    *   **Punto de entrada:** El archivo `CIPS/run.py` se encuentra en la raíz del proyecto, lo que valida su existencia como punto de entrada.