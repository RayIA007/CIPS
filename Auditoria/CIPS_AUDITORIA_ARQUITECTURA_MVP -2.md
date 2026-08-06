# CAPÍTULO 05
# BLOQUE 2
# ARQUITECTURA DEL SUBSISTEMA KNOWLEDGE, CONTEXTO Y PROMPTS

---

# 5.1 Objetivo del Subsistema

El subsistema **Knowledge → Context → Prompt** constituye el núcleo intelectual del Runtime de CIPS.

Su responsabilidad consiste en transformar una colección de módulos de conocimiento almacenados dentro del proyecto en un Prompt profesional, consistente, verificable y listo para ser enviado al proveedor LLM correspondiente.

A diferencia de un sistema tradicional de recuperación documental (RAG), este subsistema no busca información dinámica desde fuentes externas.

Todo el conocimiento utilizado proviene del propio proyecto CIPS.

Por ello, este bloque puede definirse como un **Runtime Knowledge Pipeline**, cuyo propósito consiste en:

- localizar conocimiento;
- validar su disponibilidad;
- seleccionar únicamente el conocimiento pertinente;
- comprimir el contexto cuando sea necesario;
- construir un ContextObject homogéneo;
- convertir dicho contexto en un PromptObject;
- renderizar finalmente un Prompt Markdown completamente determinista.

Todo este proceso ocurre antes de cualquier interacción con un modelo de Inteligencia Artificial.

---

# 5.2 Posición dentro del Runtime

El bloque se ejecuta inmediatamente después de que el Runtime ha determinado el Stage activo del proyecto.

La secuencia observada durante la auditoría es:

PipelineRunner

↓

KnowledgeEngine

↓

KnowledgeResolver

↓

ContextCompressor

↓

ContextEngine

↓

PromptEngine

↓

PromptRenderer

↓

Provider (OpenAI, Gemini, Claude, etc.)

↓

ValidatorEngine

↓

Storage

---

Esta arquitectura presenta una separación clara entre:

- adquisición de conocimiento;
- resolución del conocimiento;
- construcción del contexto;
- construcción del prompt;
- ejecución del modelo.

Esta separación representa uno de los mayores aciertos arquitectónicos del Runtime.

---

# 5.3 Responsabilidad General

Durante la auditoría se identificó una distribución de responsabilidades altamente cohesionada.

Cada componente posee un objetivo único.

## KnowledgeEngine

Responsabilidad exclusiva:

Cargar todos los Knowledge Modules disponibles.

No decide cuáles utilizar.

No genera contexto.

No genera prompts.

No interactúa con modelos IA.

---

## KnowledgeResolver

Responsabilidad exclusiva:

Seleccionar los módulos adecuados para el Stage actual.

No modifica contenido.

No resume conocimiento.

No construye prompts.

---

## ContextCompressor

Responsabilidad exclusiva:

Reducir el volumen del conocimiento cuando excede los límites definidos por el Runtime.

No altera el significado funcional.

No interpreta instrucciones.

No modifica reglas de negocio.

---

## ContextEngine

Responsabilidad exclusiva:

Convertir la colección de Knowledge Modules seleccionados en un único ContextObject homogéneo.

---

## PromptEngine

Responsabilidad exclusiva:

Construir un PromptObject completamente estructurado utilizando:

- contexto
- objetivo
- restricciones
- reglas editoriales
- contrato de validación

---

## PromptRenderer

Responsabilidad exclusiva:

Transformar el PromptObject en Markdown determinista listo para ser enviado al proveedor LLM.

No decide contenido.

No modifica conocimiento.

No consulta archivos.

No interactúa con el proveedor.

---

# 5.4 Flujo de Datos

El flujo observado durante la auditoría puede representarse mediante el siguiente diagrama lógico.

```text
09_KNOWLEDGE
│
├── KM-000
├── KM-001
├── KM-002
├── ...
│
▼

KnowledgeEngine

▼

Knowledge Modules

▼

KnowledgeResolver

▼

Resolved Modules

▼

ContextCompressor

▼

Compressed Modules

▼

ContextEngine

▼

ContextObject

▼

PromptEngine

▼

PromptObject

▼

PromptRenderer

▼

Markdown Prompt

▼

Provider IA
```

---

# 5.5 Principio Arquitectónico Fundamental

El Runtime implementa una filosofía muy clara:

> **La Inteligencia Artificial jamás recibe información sin haber sido previamente estructurada por CIPS.**

En otras palabras:

La IA nunca trabaja directamente con:

- archivos YAML;
- módulos Markdown;
- estructuras Runtime;
- modelos internos.

Siempre recibe un Prompt completamente construido por el Runtime.

Este principio reduce significativamente:

- ambigüedad;
- variabilidad;
- dependencia del proveedor;
- pérdida de contexto.

---

# 5.6 Separación por Capas

Durante la auditoría se identificaron cinco capas funcionales.

## Capa 1 — Knowledge

Responsables:

- KnowledgeEngine

Objetivo:

Localizar conocimiento.

---

## Capa 2 — Resolution

Responsables:

- KnowledgeResolver

Objetivo:

Determinar qué conocimiento utilizar.

---

## Capa 3 — Context

Responsables:

- ContextCompressor
- ContextEngine

Objetivo:

Construir el contexto operativo.

---

## Capa 4 — Prompt

Responsables:

- PromptEngine
- PromptRenderer

Objetivo:

Construir el Prompt profesional.

---

## Capa 5 — AI

Responsables:

Provider seleccionado.

Objetivo:

Generar el contenido solicitado.

---

# 5.7 Dependencias Observadas

La auditoría confirmó que el flujo es estrictamente unidireccional.

KnowledgeEngine

↓

KnowledgeResolver

↓

ContextEngine

↓

PromptEngine

↓

PromptRenderer

No existen ciclos.

No existen dependencias inversas.

No existen llamadas recursivas.

Este diseño simplifica considerablemente:

- mantenimiento;
- pruebas;
- sustitución de componentes;
- incorporación de nuevos proveedores.

---

# 5.8 Compatibilidad entre Pipeline Legacy y Runtime Framework

Todos los componentes auditados implementan doble interfaz de ejecución.

Modo Legacy

execute(Project)

Modo Runtime

execute(RuntimeContext)

Esta estrategia permite coexistir:

PipelineEngine

y

PipelineRunner

sin duplicar la lógica interna.

Durante la revisión del código no se identificaron implementaciones paralelas ni bifurcaciones significativas de comportamiento.

La compatibilidad se mantiene mediante adaptadores internos que extraen Project o RuntimeContext según corresponda.

---

# 5.9 Contratos de Datos

El subsistema intercambia únicamente objetos de dominio.

KnowledgeModule

↓

ContextObject

↓

PromptObject

↓

Markdown Prompt

Esto evita:

- intercambio de diccionarios arbitrarios;
- estructuras inconsistentes;
- acoplamiento entre componentes.

La utilización de modelos fuertemente tipados constituye una decisión arquitectónica acertada para la evolución futura del Runtime.

---

# 5.10 Evaluación Arquitectónica

## Cohesión

Muy alta.

Cada componente posee una responsabilidad claramente delimitada.

---

## Acoplamiento

Bajo.

Los componentes intercambian únicamente modelos del dominio.

---

## Escalabilidad

Alta.

Es posible sustituir cualquier componente sin modificar el resto del flujo.

---

## Mantenibilidad

Alta.

La división por responsabilidades facilita la localización de errores y futuras ampliaciones.

---

## Reutilización

Alta.

PromptRenderer puede reutilizarse fuera del Runtime.

KnowledgeResolver puede evolucionar independientemente del sistema de prompts.

ContextEngine puede soportar nuevas estrategias de ensamblado sin afectar al resto del pipeline.

---

# 5.11 Riesgos Detectados

Durante esta fase de auditoría no se identificaron riesgos arquitectónicos críticos.

Los riesgos existentes corresponden principalmente a evolución futura:

- incremento del número de Knowledge Modules;
- estrategias más sofisticadas de priorización;
- incorporación de recuperación híbrida;
- gestión avanzada del presupuesto de tokens.

Ninguno de estos riesgos compromete el funcionamiento actual del MVP.

---

# 5.12 Conclusión del Bloque 2.1

El subsistema Knowledge → Context → Prompt constituye una de las partes mejor estructuradas del Runtime de CIPS.

La arquitectura mantiene una separación rigurosa de responsabilidades, evita dependencias circulares, desacopla completamente la construcción del Prompt del proveedor de Inteligencia Artificial y establece una cadena de transformación determinista desde los módulos de conocimiento hasta el Prompt final.

Desde el punto de vista arquitectónico, este diseño cumple con los principios de cohesión, bajo acoplamiento, extensibilidad y mantenibilidad esperados para un MVP profesional y proporciona una base sólida para la evolución futura del Runtime.
---

# 5.13 Auditoría Arquitectónica del KnowledgeEngine

## Componente Auditado

**Archivo:**

knowledge_engine.py

**Release:** 0.4

**Build:** 019

**Estado:** RELEASE

---

# 5.14 Propósito Arquitectónico

KnowledgeEngine constituye el punto de entrada del subsistema de conocimiento.

Su única responsabilidad consiste en localizar, cargar y normalizar los Knowledge Modules requeridos por el Runtime.

No interpreta el contenido.

No determina relevancia.

No genera contexto.

No construye prompts.

No ejecuta modelos de Inteligencia Artificial.

Su función equivale al Loader del sistema de conocimiento.

Desde el punto de vista de arquitectura limpia (Clean Architecture), este componente pertenece a la capa de Infraestructura del Runtime.

---

# 5.15 Responsabilidad Única

Durante la auditoría se confirmó que el componente mantiene una responsabilidad perfectamente delimitada.

Su contrato puede resumirse como:

> Transformar la estructura física del directorio **09_KNOWLEDGE** en una colección homogénea de objetos **KnowledgeModule**.

Este principio evita mezclar:

- lógica de selección;
- lógica de contexto;
- lógica editorial;
- lógica de IA.

La cohesión interna del componente es elevada.

---

# 5.16 Punto de Entrada

El componente implementa el contrato estándar del Runtime.

```python
execute(Project)

execute(RuntimeContext)
```

Este diseño mantiene compatibilidad simultánea con:

- PipelineEngine (legado)
- PipelineRunner (nuevo Runtime)

El patrón utilizado evita duplicación de código.

Toda la lógica converge finalmente en una única implementación.

---

# 5.17 Compatibilidad del Runtime

La auditoría confirma que KnowledgeEngine identifica automáticamente el tipo recibido.

Cuando recibe:

Project

trabaja en modo Legacy.

Cuando recibe:

RuntimeContext

trabaja en modo Runtime.

Esta decisión permite reutilizar el componente sin crear versiones paralelas.

Representa una transición limpia entre ambas arquitecturas. :contentReference[oaicite:0]{index=0}

---

# 5.18 Ubicación Física del Conocimiento

Todo el conocimiento oficial del Runtime reside en:

```text
09_KNOWLEDGE/
```

Dentro de esta carpeta se localiza:

```text
00_CORE/
```

La auditoría confirma que KnowledgeEngine nunca consulta:

- Internet
- APIs
- Bases de datos
- Archivos temporales

Todo el conocimiento proviene exclusivamente del proyecto.

Este enfoque garantiza:

- reproducibilidad;
- independencia del proveedor;
- auditoría completa del conocimiento utilizado. :contentReference[oaicite:1]{index=1}

---

# 5.19 Módulos CORE

El componente declara explícitamente los módulos considerados esenciales.

```text
KM-000
KM-001
KM-002
KM-003
KM-004
KM-005
KM-006
KM-007
KM-008
```

Esta lista constituye el núcleo obligatorio del Runtime.

No depende del contenido del directorio.

Existe una definición explícita del conjunto mínimo requerido.

Este diseño evita cargas accidentales de módulos experimentales o incompletos. :contentReference[oaicite:2]{index=2}

---

# 5.20 Estrategia de Carga

El algoritmo de carga sigue una secuencia estricta.

## Paso 1

Verificar existencia de:

```text
09_KNOWLEDGE
```

↓

## Paso 2

Abrir

```text
00_CORE
```

↓

## Paso 3

Buscar módulos V2

↓

## Paso 4

Buscar módulos V1

↓

## Paso 5

Evitar duplicados

↓

## Paso 6

Ordenar por Module ID

↓

## Paso 7

Entregar lista final

La secuencia resulta sencilla, determinista y fácil de mantener.

---

# 5.21 Soporte para Dos Versiones del Sistema

Uno de los hallazgos más relevantes de la auditoría consiste en la convivencia de dos formatos de conocimiento.

## Formato V1

Archivo Markdown.

Ejemplo:

```text
KM-001.md
```

---

## Formato V2

Carpeta estructurada.

Ejemplo:

```text
KM-001/

METADATA.yaml

RUNTIME.yaml
```

KnowledgeEngine soporta ambos simultáneamente.

Esta compatibilidad facilita la migración progresiva del conocimiento sin romper proyectos existentes. :contentReference[oaicite:3]{index=3}

---

# 5.22 Prioridad de Versiones

Cuando existen dos versiones del mismo módulo:

V2

y

V1

el Runtime utiliza siempre la versión V2.

La versión Markdown únicamente se carga cuando no existe equivalente estructurado.

Este comportamiento elimina inconsistencias entre versiones y establece una jerarquía clara de precedencia.

---

# 5.23 Conversión a Modelo de Dominio

Independientemente del origen físico, todos los módulos terminan convertidos en:

```text
KnowledgeModule
```

Este objeto contiene:

- module_id
- nombre
- categoría
- contenido
- dependencias
- metadatos

A partir de este punto, el resto del Runtime deja de conocer el formato físico original.

Esta abstracción reduce el acoplamiento entre capas.

---

# 5.24 Conversión de YAML Operativo

Uno de los aspectos más interesantes observados es la transformación de:

```text
RUNTIME.yaml
```

en texto operativo.

El componente genera automáticamente una representación textual estructurada.

Por ejemplo:

```yaml
dependencies:
 - KM-001
```

se transforma internamente en bloques Markdown equivalentes.

Esta decisión unifica el tratamiento del conocimiento para ContextEngine, independientemente de su origen físico. :contentReference[oaicite:4]{index=4}

---

# 5.25 Normalización de Dependencias

Las dependencias reciben tratamiento específico.

En módulos V1:

se detectan mediante expresiones regulares.

En módulos V2:

se leen directamente desde:

```text
RUNTIME.yaml
```

Finalmente ambas terminan representadas mediante la misma estructura:

```python
list[str]
```

Esto simplifica enormemente el trabajo posterior del Runtime.

---

# 5.26 Metadatos Generados

KnowledgeEngine incorpora información útil para trazabilidad.

Entre ella:

- componente
- project_id
- cantidad de módulos
- ids cargados
- módulos V1
- módulos V2
- ruta origen

Estos metadatos resultan especialmente valiosos para:

- depuración;
- auditoría;
- diagnóstico;
- validación del Runtime. :contentReference[oaicite:5]{index=5}

---

# 5.27 Gestión de Errores

La estrategia de errores es consistente.

Se contemplan escenarios como:

- inexistencia del directorio principal;
- ausencia de módulos CORE;
- errores inesperados;
- rutas inválidas.

Todos ellos producen un:

```text
EngineResult.fail()
```

con:

- mensaje;
- lista de errores;
- metadatos.

No se identificaron excepciones sin controlar.

---

# 5.28 Calidad del Diseño

## Cohesión

Muy alta.

Todas las funciones participan exclusivamente en la carga del conocimiento.

---

## Acoplamiento

Bajo.

El componente depende únicamente de:

- RuntimeContext
- Project
- KnowledgeModule
- utilidades YAML

No conoce ContextEngine.

No conoce PromptEngine.

No conoce proveedores IA.

---

## Legibilidad

Alta.

Los métodos son pequeños.

Los nombres descriptivos.

Existe separación clara de responsabilidades.

---

## Extensibilidad

Alta.

Resulta sencillo incorporar nuevos formatos de módulo sin alterar la interfaz pública.

---

# 5.29 Fortalezas Detectadas

Durante la auditoría se identificaron las siguientes fortalezas:

- Compatibilidad Legacy + Runtime.
- Compatibilidad V1 + V2.
- Conversión homogénea a KnowledgeModule.
- Priorización automática de módulos modernos.
- Gestión consistente de errores.
- Generación rica de metadatos.
- Ordenamiento determinista.
- Ausencia de dependencias circulares.
- Código altamente modular.

---

# 5.30 Riesgos Detectados

No se detectaron riesgos críticos.

Únicamente se observaron oportunidades de evolución:

- incorporación de caché de módulos para reducir lecturas repetidas;
- carga diferida (lazy loading) para proyectos con cientos de módulos;
- validación criptográfica o checksum de módulos críticos;
- soporte para perfiles de conocimiento (CORE, VIDEO, BLOG, TIKTOK, etc.).

Estas mejoras incrementarían el rendimiento y la escalabilidad, pero no afectan la estabilidad del MVP.

---

# 5.31 Evaluación Final del KnowledgeEngine

| Criterio | Evaluación |
|----------|------------|
| Cohesión | Excelente |
| Acoplamiento | Muy Bajo |
| Escalabilidad | Alta |
| Legibilidad | Excelente |
| Compatibilidad | Excelente |
| Robustez | Alta |
| Preparado para MVP | Sí |
| Preparado para evolución futura | Sí |

---

# 5.32 Conclusión del Componente

KnowledgeEngine cumple correctamente el papel de cargador oficial del conocimiento del Runtime.

La implementación observada mantiene una separación rigurosa entre almacenamiento físico y representación lógica, soporta simultáneamente múltiples generaciones de módulos, genera modelos homogéneos para el resto del pipeline y proporciona una base estable sobre la cual operan `KnowledgeResolver`, `ContextEngine` y los componentes posteriores.

Desde la perspectiva arquitectónica, el componente presenta un diseño sólido, altamente mantenible y alineado con los principios de responsabilidad única, bajo acoplamiento y extensibilidad, constituyendo un punto de partida confiable para el procesamiento del conocimiento dentro del MVP de CIPS.