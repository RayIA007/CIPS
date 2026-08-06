---

# CAPÍTULO 06

# BLOQUE 3 — PROVEEDORES Y RESPUESTA DEL LLM

---

# 6.1 Arquitectura General del Subsistema LLM

## Objetivo

El Subsistema LLM constituye la capa encargada de establecer la comunicación entre el Runtime de CIPS y cualquier proveedor de Inteligencia Artificial.

Su responsabilidad consiste en recibir un Prompt completamente construido por el Runtime, enviarlo al proveedor configurado, obtener una respuesta estructurada y devolverla nuevamente al Runtime mediante un contrato uniforme, independientemente del proveedor utilizado.

La arquitectura garantiza que el resto del sistema permanezca completamente desacoplado de SDK, APIs, modelos y servicios específicos.

---

# 6.2 Filosofía Arquitectónica

La arquitectura del subsistema LLM sigue un diseño basado en contratos e inversión de dependencias.

El Runtime nunca interactúa directamente con:

- Google Gemini
- OpenAI
- Claude
- Ollama
- LM Studio
- APIs REST
- SDK propietarios

Toda interacción ocurre exclusivamente mediante la interfaz abstracta:

```text
LLMProvider
```

Esto permite sustituir cualquier proveedor sin modificar el Pipeline.

---

# 6.3 Objetivos del Diseño

El subsistema fue diseñado para cumplir los siguientes objetivos:

- independencia del proveedor;
- facilidad para incorporar nuevos modelos;
- compatibilidad entre ejecución manual y automática;
- reutilización del Pipeline existente;
- desacoplamiento entre Runtime y SDK;
- manejo uniforme de errores;
- metadatos homogéneos;
- extensibilidad mediante Factory;
- configuración externa.

---

# 6.4 Componentes del Subsistema

La auditoría identificó los siguientes componentes principales.

```text
LLMAdapter

↓

LLMProviderFactory

↓

LLMProvider

↓

ProviderResult

↓

Proveedor Concreto

↓

SDK/API

↓

LLMResponse

↓

RuntimeContext
```

Cada componente posee una responsabilidad única.

---

# 6.5 Flujo General del Subsistema

El flujo de ejecución observado durante la auditoría es el siguiente.

```text
Prompt Markdown

↓

RuntimeContext

↓

LLMAdapter

↓

LLMProviderFactory

↓

Proveedor configurado

↓

SDK/API

↓

Respuesta

↓

ProviderResult

↓

LLMResponse

↓

RuntimeContext

↓

Pipeline
```

---

# 6.6 Principios Arquitectónicos

El diseño cumple los siguientes principios.

## Separación de responsabilidades

Cada componente realiza únicamente una función.

---

## Bajo acoplamiento

El Pipeline desconoce completamente el proveedor utilizado.

---

## Configuración externa

La selección del proveedor se realiza mediante configuración.

---

## Sustitución transparente

Puede cambiarse un proveedor sin modificar el Runtime.

---

## Uniformidad

Todos los proveedores devuelven exactamente el mismo contrato.

---

## Compatibilidad

La arquitectura soporta simultáneamente ejecución:

- manual;
- automática;
- simulada.

---

# 6.7 Papel del Runtime

El Runtime no posee conocimiento acerca de:

- SDK utilizados;
- endpoints;
- autenticación;
- tokens;
- APIs;
- modelos.

Su única dependencia consiste en:

```text
LLMProvider
```

Este desacoplamiento constituye uno de los pilares de la arquitectura.

---

# 6.8 Configuración Declarativa

La auditoría confirma que el comportamiento del subsistema LLM se encuentra gobernado mediante archivos YAML.

La configuración externa permite definir:

- proveedor activo;
- modelo;
- temperatura;
- presupuesto máximo de salida;
- timeout;
- proveedor manual;
- preferencias por Stage;
- políticas de fallback;
- parámetros específicos del proveedor.

Como consecuencia, las decisiones operativas permanecen fuera del código del Pipeline.

---

# 6.9 Patrón Arquitectónico

El subsistema implementa una combinación de patrones ampliamente utilizados.

## Adapter

Representado por:

```text
LLMAdapter
```

---

## Factory

Representado por:

```text
LLMProviderFactory
```

---

## Strategy

Representado por:

```text
LLMProvider
```

y sus implementaciones concretas.

---

## Result Object

Representado por:

```text
ProviderResult
```

---

## Dependency Injection

El proveedor puede inyectarse explícitamente o resolverse mediante configuración.

---

# 6.10 Beneficios del Diseño

La arquitectura permite:

- incorporar nuevos proveedores;
- reutilizar el Pipeline;
- reutilizar RuntimeContext;
- mantener un único flujo de ejecución;
- facilitar pruebas;
- ejecutar el sistema sin Internet;
- ejecutar el sistema con múltiples proveedores;
- realizar migraciones sin afectar el Runtime.

---

# 6.11 Componentes Auditados

Durante la auditoría fueron identificados los siguientes componentes.

| Componente | Función |
|------------|---------|
| LLMAdapter | Comunicación Runtime ↔ LLM |
| LLMProvider | Contrato oficial |
| ProviderResult | Resultado uniforme |
| LLMProviderFactory | Creación de proveedores |
| LLMManager | Administración de proveedores |
| ManualLLMProvider | Ejecución manual |
| GeminiLLMProvider | Integración Google Gemini |
| OpenAIProvider | Integración OpenAI |
| MockProvider | Simulación local |

---

# 6.12 Objetos del Dominio

Durante todo el flujo únicamente se utilizan objetos bien definidos.

```text
Prompt Markdown

↓

ProviderResult

↓

LLMResponse

↓

RuntimeContext

↓

EngineResult
```

No existen estructuras arbitrarias intercambiadas entre componentes.

---

# 6.13 Separación entre Runtime y Proveedores

La auditoría confirma que el Runtime únicamente conoce el contrato abstracto.

```text
Runtime

↓

LLMAdapter

↓

LLMProvider

↓

Proveedor Concreto
```

En consecuencia:

- cambiar Gemini por OpenAI;
- incorporar Claude;
- integrar Ollama;
- utilizar LM Studio;
- utilizar Azure;

no requiere modificar el Pipeline principal.

---

# 6.14 Evaluación General del Subsistema

El Subsistema LLM presenta una arquitectura altamente modular basada en contratos, donde la comunicación con los modelos de Inteligencia Artificial queda completamente encapsulada detrás de un conjunto reducido de componentes especializados.

La combinación de Adapter, Factory y Strategy proporciona un alto grado de extensibilidad, facilita las pruebas mediante proveedores simulados y permite coexistir modos manuales y automáticos sin alterar el flujo general del Runtime.

La utilización de configuración declarativa y contratos uniformes reduce el acoplamiento, favorece la mantenibilidad y prepara la plataforma para incorporar nuevos proveedores o capacidades sin modificar la arquitectura principal.

Este diseño cumple adecuadamente los objetivos definidos para el MVP y constituye una base sólida para la evolución futura del ecosistema CIPS.
---

# CAPÍTULO 07

# BLOQUE 4 — PERSISTENCIA, VALIDACIÓN Y MEMORIA

---

# 7.1 Arquitectura General

## Objetivo

El Bloque de Persistencia, Validación y Memoria constituye el mecanismo encargado de conservar el estado del proyecto, validar automáticamente la calidad de las respuestas producidas por los modelos de Inteligencia Artificial y mantener la trazabilidad completa del Pipeline.

Mientras los bloques anteriores construyen conocimiento, contexto y prompts, este bloque determina si una respuesta puede continuar dentro del flujo oficial de producción.

En consecuencia, este subsistema representa el mecanismo de control de calidad del Runtime.

---

# 7.2 Responsabilidades

Durante la auditoría fueron identificadas tres responsabilidades principales.

## Persistencia

Administrar la estructura física del proyecto.

---

## Validación

Determinar automáticamente si una respuesta cumple los criterios mínimos de calidad.

---

## Memoria

Registrar el historial de ejecución del proyecto y calcular el siguiente Stage.

---

# 7.3 Componentes Auditados

| Componente | Responsabilidad |
|------------|-----------------|
| ProjectManager | Administración del proyecto |
| ValidatorEngine | Validación profesional |
| MemoryEngine | Persistencia del historial |
| validation_rules.yaml | Configuración declarativa de validación |

---

# 7.4 Flujo General

```text
Respuesta LLM

↓

ValidatorEngine

↓

ValidationResult

↓

MemoryEngine

↓

memoria.yaml

↓

ProjectManager

↓

proyecto.yaml

↓

Pipeline
```

---

# 7.5 Filosofía Arquitectónica

Este bloque adopta una arquitectura basada en separación de responsabilidades.

Cada componente realiza únicamente una función.

ProjectManager administra el proyecto.

ValidatorEngine determina la calidad.

MemoryEngine conserva la memoria.

Las reglas permanecen completamente separadas del código mediante archivos YAML.

---

# 7.6 Persistencia del Proyecto

La auditoría confirma que toda la persistencia del proyecto se realiza mediante archivos legibles por el usuario.

No existe una base de datos.

La información permanece almacenada mediante:

- proyecto.yaml
- memoria.yaml
- archivos Markdown
- directorios del proyecto

Esta decisión favorece:

- transparencia;
- portabilidad;
- facilidad de respaldo;
- inspección manual.

---

# 7.7 ProjectManager

## Objetivo

ProjectManager constituye el administrador oficial del ciclo de vida del proyecto.

Sus responsabilidades incluyen:

- crear proyectos;
- numerar proyectos;
- generar UUID;
- crear directorios;
- generar archivos iniciales;
- cargar proyectos;
- actualizar el Stage activo.

---

## Creación del Proyecto

La creación de un proyecto comprende:

- generación del identificador;
- creación del UUID;
- creación de carpetas;
- generación de proyecto.yaml;
- generación de memoria.yaml;
- creación de documentos Markdown iniciales.

Todo el proceso ocurre automáticamente.

---

## Organización Física

Cada proyecto mantiene una estructura estandarizada.

```text
PROYECTO_xxxx

01_FUENTES

02_PROMPTS

03_RESPUESTAS

04_CONTENIDO

05_RECURSOS

06_EXPORTACIONES

proyecto.yaml

memoria.yaml

CONTEXTO.md

00_TEMA.md

...
```

Esta organización facilita la trazabilidad completa del Pipeline.

---

## Estado del Proyecto

ProjectManager mantiene:

- stage_actual;
- ultimo_stage_validado;
- estado;
- fecha_actualizacion.

Estos valores permiten reanudar el Pipeline sin pérdida de contexto.

---

# 7.8 ValidatorEngine

## Objetivo

ValidatorEngine constituye el mecanismo oficial de control de calidad del Runtime.

Su responsabilidad consiste en determinar automáticamente si una respuesta producida por un modelo IA posee la calidad suficiente para continuar dentro del Pipeline.

---

## Filosofía

El sistema no acepta respuestas únicamente porque fueron generadas por un modelo.

Toda respuesta debe superar una evaluación objetiva.

---

## Flujo

```text
LLMResponse

↓

Análisis

↓

Puntuación

↓

ValidationResult

↓

Pipeline
```

---

## Criterios Analizados

Durante la auditoría fueron identificados los siguientes grupos de validación.

### Longitud

Se analiza:

- caracteres;
- palabras.

---

### Estructura

Se verifica:

- encabezados;
- encabezados obligatorios;
- encabezados recomendados.

---

### Completitud

Se analiza:

- cantidad de oraciones;
- posibles truncamientos.

---

### Restricciones

Se detecta:

- filtración del prompt;
- negativas del modelo;
- texto genérico;
- lenguaje sensacionalista.

---

### Calidad

Se calcula:

- repetición;
- legibilidad;
- puntuación total.

---

# 7.9 Sistema de Puntuación

La validación produce una puntuación entre:

```text
0

↓

100
```

La aprobación depende de:

- puntuación mínima;
- ausencia de errores críticos;
- cumplimiento estructural.

---

## Componentes de la puntuación

La puntuación combina cinco factores.

- Longitud
- Estructura
- Completitud
- Restricciones
- Calidad

Cada uno posee un peso configurable.

---

# 7.10 ValidationResult

El resultado de la validación se encapsula mediante un único objeto.

```text
ValidationResult
```

Este objeto contiene:

- approved;
- warnings;
- observations;
- errors;
- metadata.

Todo el Runtime utiliza este mismo contrato.

---

# 7.11 validation_rules.yaml

## Objetivo

Las reglas de validación permanecen completamente fuera del código.

Esto permite modificar el comportamiento del validador sin recompilar el sistema.

---

## Configuración

El archivo gobierna:

- puntuación mínima;
- pesos;
- longitud mínima;
- encabezados;
- reglas por Stage;
- detección de truncamiento;
- detección de filtración;
- restricciones;
- calidad.

---

## Beneficios

Separar las reglas del código ofrece:

- flexibilidad;
- mantenibilidad;
- auditoría;
- adaptación por proyecto.

---

# 7.12 MemoryEngine

## Objetivo

MemoryEngine constituye el mecanismo oficial de memoria del Runtime.

Su función consiste en registrar únicamente los Stages que superaron exitosamente la validación.

---

## Flujo

```text
ValidationResult

↓

MemoryRecord

↓

memoria.yaml

↓

RuntimeContext
```

---

## Condición de Escritura

La memoria únicamente se actualiza cuando:

```text
ValidationResult.approved == True
```

Las respuestas rechazadas nunca modifican el historial.

Esta decisión protege la consistencia del proyecto.

---

## Información Registrada

Cada registro almacena:

- Stage;
- estado;
- resumen;
- siguiente Stage;
- advertencias;
- observaciones;
- fecha;
- identificador del proyecto.

---

## Cálculo del siguiente Stage

MemoryEngine determina automáticamente el siguiente Stage utilizando la secuencia oficial del Pipeline.

Cuando el proyecto alcanza el último Stage, el sistema devuelve el Stage final.

---

# 7.13 Persistencia del Historial

El historial mantiene una estructura acumulativa.

```text
Historial

↓

Stage 1

↓

Stage 2

↓

Stage 3

↓

...

↓

Stage Final
```

Cada ejecución aprobada añade un nuevo registro.

Nunca sobrescribe el historial existente.

---

# 7.14 Integración con RuntimeContext

El bloque interactúa directamente con RuntimeContext.

ValidatorEngine registra:

```text
validation_result
```

MemoryEngine registra:

```text
memory_data
```

De esta forma el Pipeline conserva toda la información necesaria para continuar la ejecución.

---

# 7.15 Integración entre Componentes

```text
ProjectManager

↓

Project

↓

ValidatorEngine

↓

ValidationResult

↓

MemoryEngine

↓

RuntimeContext

↓

Pipeline
```

Cada componente produce información para el siguiente.

---

# 7.16 Principios Arquitectónicos

La auditoría identifica los siguientes principios.

## Persistencia desacoplada

Toda la persistencia se realiza mediante archivos YAML y Markdown.

---

## Validación objetiva

La aceptación de una respuesta depende de reglas medibles.

---

## Memoria incremental

El historial nunca se destruye.

---

## Configuración externa

Las reglas permanecen fuera del código.

---

## Compatibilidad

Los componentes mantienen compatibilidad tanto con el Runtime Framework como con la interfaz heredada.

---

# 7.17 Fortalezas

Durante la auditoría se identificaron las siguientes fortalezas.

- Persistencia completamente transparente.
- Ausencia de dependencias con bases de datos.
- Historial completo del proyecto.
- Validación objetiva basada en puntuación.
- Configuración declarativa.
- Compatibilidad entre arquitectura nueva y legado.
- Bajo acoplamiento.
- Fácil auditoría.
- Facilidad para incorporar nuevas reglas.

---

# 7.18 Riesgos

Los principales riesgos identificados son:

- crecimiento indefinido del historial de memoria;
- dependencia de reglas correctamente configuradas;
- ausencia de versionado de reglas de validación;
- posible incremento del costo de validación al ampliar el número de criterios.

---

# 7.19 Cumplimiento del MVP

El Bloque de Persistencia, Validación y Memoria cumple los objetivos definidos para el MVP.

Proporciona:

- administración completa del proyecto;
- validación automática de respuestas;
- persistencia del estado;
- memoria histórica;
- continuidad entre Stages;
- configuración declarativa;
- compatibilidad con la arquitectura Runtime.

---

# 7.20 Conclusiones

La auditoría demuestra que este bloque constituye el mecanismo responsable de preservar la integridad del Pipeline.

Mientras ProjectManager administra el ciclo de vida físico del proyecto, ValidatorEngine garantiza la calidad mínima de las respuestas producidas por los modelos IA y MemoryEngine conserva la trazabilidad completa de los Stages aprobados.

La separación entre persistencia, validación y memoria reduce el acoplamiento entre componentes, facilita la evolución independiente de cada subsistema y permite mantener un flujo determinista donde únicamente las respuestas que satisfacen las reglas oficiales continúan dentro del Pipeline.

La utilización de archivos YAML para la configuración y archivos Markdown para la persistencia del contenido mantiene la transparencia del sistema, simplifica las tareas de auditoría y elimina la dependencia de mecanismos externos de almacenamiento, cumpliendo adecuadamente los objetivos establecidos para el MVP.