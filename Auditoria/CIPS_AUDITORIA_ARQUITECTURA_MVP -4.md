---

# 5.81 Auditoría Arquitectónica del PromptBuilder, PromptEngine y PromptRenderer

## Componentes Auditados

**Archivos:**

- prompt_builder.py
- prompt_engine.py
- prompt_renderer.py

**Estado:**

RELEASE

---

# 5.82 Propósito del Subsistema de Prompts

El subsistema de Prompts constituye la última etapa del Runtime antes de entregar información al proveedor de Inteligencia Artificial.

Su responsabilidad consiste en transformar un **ContextObject**, construido previamente por el Runtime, en un Prompt profesional, estructurado, verificable y completamente determinista.

A diferencia de arquitecturas tradicionales donde el Prompt se construye directamente mediante cadenas de texto dispersas por el código, CIPS implementa un pipeline de construcción compuesto por tres niveles claramente diferenciados:

```text
ContextObject

↓

PromptBuilder

↓

PromptObject

↓

PromptEngine

↓

Prompt Markdown

↓

PromptRenderer

↓

Prompt Final

↓

Provider IA
```

Cada componente participa únicamente en una parte del proceso, evitando responsabilidades cruzadas y facilitando la evolución independiente del sistema.

---

# 5.83 Filosofía Arquitectónica

Durante la auditoría se confirmó que el Runtime adopta un principio fundamental:

> **El Prompt no es una cadena de texto; el Prompt es un objeto de dominio construido mediante una secuencia controlada de transformaciones.**

Este enfoque elimina una de las principales fuentes de errores presentes en muchos sistemas basados en LLM:

- concatenaciones manuales;
- instrucciones duplicadas;
- prompts inconsistentes;
- pérdida de estructura;
- diferencias entre proveedores.

La arquitectura convierte la construcción del Prompt en un proceso reproducible y verificable.

---

# 5.84 Separación de Responsabilidades

Los tres componentes poseen responsabilidades completamente independientes.

## PromptBuilder

Responsabilidad:

Construir el PromptObject.

No genera Markdown.

No renderiza variables.

No guarda archivos.

No conoce proveedores.

---

## PromptEngine

Responsabilidad:

Construir el contrato operativo del Prompt.

Añadir objetivos.

Agregar restricciones.

Definir estructura obligatoria.

Cargar reglas de validación.

Guardar el Prompt generado.

---

## PromptRenderer

Responsabilidad:

Transformar PromptObject en Markdown determinista.

Resolver variables.

Normalizar el texto.

Renderizar listas.

Renderizar encabezados.

No modifica conocimiento.

No interpreta contenido.

No interactúa con proveedores IA. :contentReference[oaicite:0]{index=0}

---

# 5.85 PromptBuilder

## Propósito

PromptBuilder representa la primera etapa del subsistema.

Su función consiste en convertir el ContextObject producido por ContextEngine en un PromptObject completamente estructurado.

Este objeto constituye el contrato oficial utilizado por los componentes posteriores.

---

# 5.86 Construcción del PromptObject

La auditoría permitió identificar que PromptBuilder encapsula elementos esenciales como:

- proyecto;
- objetivo;
- contexto;
- formato esperado;
- restricciones;
- metadatos.

A partir de este momento desaparecen las dependencias directas respecto al ContextObject.

Todo el Runtime trabaja exclusivamente mediante PromptObject.

---

# 5.87 Ventajas del Modelo

La utilización de PromptObject ofrece diversas ventajas arquitectónicas:

- independencia respecto al formato final;
- posibilidad de múltiples renderizadores;
- validación previa del Prompt;
- serialización sencilla;
- pruebas unitarias simplificadas.

Este patrón reduce considerablemente el acoplamiento entre la lógica de negocio y la representación textual.

---

# 5.88 PromptEngine

## Propósito

PromptEngine representa el verdadero constructor del Prompt operativo.

Mientras PromptBuilder crea el modelo de dominio, PromptEngine lo completa con todas las reglas necesarias para que el ValidatorEngine pueda evaluar posteriormente la respuesta generada.

---

# 5.89 Entrada del Componente

PromptEngine recibe:

- Project;
- RuntimeContext;
- ContextObject.

Su producto principal es:

```text
PromptObject
```

junto con un Prompt Markdown almacenado dentro del proyecto. :contentReference[oaicite:1]{index=1}

---

# 5.90 Carga de Reglas de Validación

Uno de los hallazgos más importantes de la auditoría consiste en que PromptEngine no contiene reglas editoriales codificadas directamente.

Todas las reglas se leen desde:

```text
01_CONFIG/

validation_rules.yaml
```

Entre ellas:

- longitud mínima;
- palabras mínimas;
- puntuación requerida;
- encabezados obligatorios;
- encabezados recomendados.

Este diseño desacopla completamente la lógica editorial del código Python. :contentReference[oaicite:2]{index=2}

---

# 5.91 Construcción del Contrato de Salida

PromptEngine construye un contrato operativo para cada Stage.

Este contrato contiene, entre otros elementos:

- Stage activo;
- longitud mínima;
- palabras mínimas;
- encabezados obligatorios;
- encabezados recomendados;
- puntuación mínima.

Posteriormente dicho contrato será utilizado por ValidatorEngine para evaluar automáticamente la respuesta producida por el modelo.

Esta decisión convierte el Prompt en un documento verificable.

---

# 5.92 Objetivos por Stage

La auditoría confirma que PromptEngine mantiene objetivos específicos para cada etapa del proyecto.

Ejemplos:

Investigación

↓

Realizar investigación confiable.

---

Verificación

↓

Clasificar evidencia.

---

Guion

↓

Construir guion listo para producción.

---

Storyboard

↓

Transformar el guion en estructura visual.

Cada Stage posee un objetivo claramente definido, evitando instrucciones ambiguas para el modelo. :contentReference[oaicite:3]{index=3}

---

# 5.93 Restricciones Editoriales

PromptEngine incorpora restricciones generales destinadas a preservar la calidad del contenido.

Entre ellas destacan:

- no inventar datos;
- no exagerar beneficios;
- distinguir hechos de opiniones;
- evitar lenguaje sensacionalista;
- respetar la evidencia disponible;
- no copiar instrucciones internas.

Estas restricciones forman parte del Prompt final enviado al proveedor IA. :contentReference[oaicite:4]{index=4}

---

# 5.94 Encabezados Obligatorios

El componente genera automáticamente la estructura mínima requerida para el Stage.

El Prompt indica explícitamente:

- encabezados obligatorios;
- encabezados recomendados;
- reglas de utilización.

Esta decisión facilita que ValidatorEngine pueda comprobar posteriormente la estructura del documento generado.

---

# 5.95 Persistencia del Prompt

Una característica particularmente interesante consiste en que PromptEngine guarda automáticamente el Prompt Markdown dentro del proyecto.

Ruta observada:

```text
02_PROMPTS/

PROMPT_<STAGE>.md
```

Este comportamiento aporta trazabilidad completa y permite reconstruir exactamente qué instrucciones fueron enviadas al proveedor durante una ejecución determinada. :contentReference[oaicite:5]{index=5}

---

# 5.96 Integración con RuntimeContext

En modo Runtime el componente incorpora al contexto:

- PromptObject;
- Prompt Markdown;
- ruta del Prompt;
- contrato de validación.

Los motores posteriores reutilizan esta información sin necesidad de reconstruir el Prompt.

---

# 5.97 PromptRenderer

## Propósito

PromptRenderer constituye el último componente antes del proveedor LLM.

Su responsabilidad consiste exclusivamente en convertir PromptObject en texto Markdown listo para enviarse al modelo.

No modifica contenido.

No agrega conocimiento.

No consulta archivos.

No persiste información. :contentReference[oaicite:6]{index=6}

---

# 5.98 Renderización Determinista

Uno de los aspectos más sólidos observados durante la auditoría consiste en que PromptRenderer produce siempre el mismo resultado para el mismo PromptObject.

No intervienen procesos aleatorios.

No depende del proveedor IA.

No incorpora heurísticas variables.

Este comportamiento favorece:

- reproducibilidad;
- auditorías;
- pruebas unitarias;
- depuración.

---

# 5.99 Resolución de Variables

PromptRenderer soporta plantillas mediante expresiones:

```text
{{ variable }}
```

y rutas anidadas como:

```text
{{ project.project_id }}
```

Las variables son resueltas utilizando:

- atributos;
- dataclasses;
- diccionarios;
- estructuras anidadas.

Cuando falta alguna variable, el componente puede trabajar en modo estricto o generar advertencias controladas. :contentReference[oaicite:7]{index=7}

---

# 5.100 Construcción de Secciones

La auditoría permitió reconstruir la estructura utilizada por PromptRenderer.

El Prompt final incluye secciones como:

- Identidad del proyecto.
- Objetivo.
- Contexto disponible.
- Módulos utilizados.
- Restricciones.
- Formato esperado.
- Instrucción final.

Todas ellas son generadas automáticamente a partir del PromptObject. :contentReference[oaicite:8]{index=8}

---

# 5.101 Normalización del Texto

Antes de finalizar la renderización el componente:

- elimina saltos redundantes;
- normaliza listas;
- convierte estructuras complejas;
- estabiliza el formato Markdown.

Este proceso garantiza uniformidad entre diferentes ejecuciones.

---

# 5.102 Calidad Arquitectónica

## Cohesión

Excelente.

Cada componente participa únicamente en la construcción del Prompt.

---

## Acoplamiento

Muy bajo.

Los tres componentes intercambian exclusivamente:

- ContextObject;
- PromptObject;
- Markdown.

No conocen el proveedor IA.

No conocen ValidatorEngine.

No conocen Storage.

---

## Extensibilidad

Muy alta.

Resulta posible incorporar nuevos renderizadores (HTML, JSON, XML, etc.) reutilizando el mismo PromptObject.

---

## Reutilización

Alta.

PromptRenderer puede utilizarse fuera del Runtime para renderizar cualquier PromptObject compatible.

---

# 5.103 Fortalezas Detectadas

Durante la auditoría se identificaron las siguientes fortalezas:

- Separación clara entre modelo y representación.
- Construcción determinista.
- Contratos de validación externos.
- Persistencia automática del Prompt.
- Renderización independiente del proveedor.
- Resolución robusta de variables.
- Excelente integración con RuntimeContext.
- Muy bajo acoplamiento.
- Alta cohesión.

---

# 5.104 Oportunidades de Evolución

Aunque el diseño actual resulta adecuado para el MVP, podrían incorporarse futuras capacidades.

## PromptBuilder

- múltiples estrategias de construcción;
- plantillas específicas por plataforma.

---

## PromptEngine

- contratos dinámicos según proveedor;
- restricciones adaptativas;
- presupuestos automáticos de tokens.

---

## PromptRenderer

- renderizadores HTML;
- renderizadores JSON;
- renderizadores XML;
- renderizadores específicos por proveedor;
- soporte para múltiples idiomas.

Estas mejoras ampliarían la flexibilidad sin alterar la arquitectura existente.

---

# 5.105 Evaluación Arquitectónica

| Criterio | PromptBuilder | PromptEngine | PromptRenderer |
|----------|---------------|--------------|----------------|
| Cohesión | Excelente | Excelente | Excelente |
| Acoplamiento | Muy Bajo | Muy Bajo | Muy Bajo |
| Escalabilidad | Alta | Alta | Alta |
| Legibilidad | Excelente | Excelente | Excelente |
| Compatibilidad Runtime | Completa | Completa | Completa |
| Preparado para MVP | Sí | Sí | Sí |

---

# 5.106 Relación con el Pipeline

El subsistema de Prompts constituye la transición definitiva entre el Runtime y el proveedor de Inteligencia Artificial.

Su posición puede resumirse mediante el siguiente esquema:

```text
ContextEngine

↓

PromptBuilder

↓

PromptEngine

↓

PromptRenderer

↓

ProviderEngine
```

La existencia de tres componentes especializados permite desacoplar completamente la construcción lógica del Prompt, su enriquecimiento con contratos de validación y su representación final en Markdown.

---

# 5.107 Conclusión del Subsistema de Prompts

La auditoría confirma que el subsistema de Prompts es una de las áreas con mayor madurez arquitectónica dentro del Runtime de CIPS.

La separación entre **PromptBuilder**, **PromptEngine** y **PromptRenderer** transforma la generación de instrucciones para modelos de Inteligencia Artificial en un proceso controlado, determinista y verificable.

La utilización de `PromptObject` como contrato de dominio, la externalización de reglas mediante `validation_rules.yaml`, la generación automática de contratos de salida y la renderización independiente del proveedor constituyen decisiones de diseño que reducen el acoplamiento, incrementan la mantenibilidad y preparan al sistema para incorporar nuevos proveedores y formatos sin modificar la lógica central del Runtime.

Desde la perspectiva arquitectónica, este subsistema cumple plenamente con los principios de responsabilidad única, separación de capas, extensibilidad y trazabilidad, proporcionando una base sólida para la interacción confiable entre el Runtime de CIPS y cualquier proveedor LLM compatible.
---

# 5.108 Flujo Completo del Subsistema Knowledge → Context → Prompt

## Objetivo del Flujo

Una vez auditados todos los componentes que conforman el Subsistema de Knowledge, Contexto y Prompts, es posible reconstruir el flujo completo de información dentro del Runtime de CIPS.

El objetivo de este flujo consiste en transformar un conjunto de módulos de conocimiento almacenados dentro del proyecto en un Prompt profesional, estructurado y verificable, listo para ser procesado por un proveedor de Inteligencia Artificial.

Durante toda la secuencia no existe interacción directa con ningún modelo LLM.

La Inteligencia Artificial únicamente interviene cuando el Prompt ha sido completamente construido y validado por el Runtime.

---

# 5.109 Flujo General del Subsistema

El flujo identificado durante la auditoría puede representarse mediante el siguiente diagrama de alto nivel.

```text
                 STAGE ACTUAL
                        │
                        ▼
               KnowledgeEngine
                        │
                        ▼
        Carga de Knowledge Modules
                        │
                        ▼
             KnowledgeResolver
                        │
                        ▼
      Selección de módulos relevantes
                        │
                        ▼
            ContextCompressor
                        │
                        ▼
      Ajuste del presupuesto de contexto
                        │
                        ▼
              ContextEngine
                        │
                        ▼
               ContextObject
                        │
                        ▼
              PromptBuilder
                        │
                        ▼
                PromptObject
                        │
                        ▼
               PromptEngine
                        │
                        ▼
         Contrato + Restricciones
                        │
                        ▼
             PromptRenderer
                        │
                        ▼
         Prompt Markdown Final
                        │
                        ▼
              Provider LLM
```

---

# 5.110 Flujo Detallado de Transformación

La auditoría permitió reconstruir la secuencia exacta de transformación de la información.

## Etapa 1

Entrada

```text
09_KNOWLEDGE/
```

↓

KnowledgeEngine

↓

Lista de KnowledgeModule

---

## Etapa 2

KnowledgeResolver

↓

KnowledgeModule seleccionados

↓

Dependencias resueltas

↓

Duplicados eliminados

---

## Etapa 3

ContextCompressor

↓

Verificación del presupuesto de contexto

↓

Compresión determinista (si aplica)

---

## Etapa 4

ContextEngine

↓

ContextObject

---

## Etapa 5

PromptBuilder

↓

PromptObject

---

## Etapa 6

PromptEngine

↓

Contrato de validación

↓

Restricciones editoriales

↓

Objetivos del Stage

↓

Prompt Markdown

---

## Etapa 7

PromptRenderer

↓

Renderización

↓

Resolución de variables

↓

Normalización

↓

Prompt Final

---

## Etapa 8

Provider IA

↓

Respuesta

↓

ValidatorEngine

↓

Storage

---

# 5.111 Evolución del Objeto Principal

Uno de los aspectos más relevantes identificados durante la auditoría es la evolución gradual del modelo de datos.

```text
Archivos Markdown / YAML

↓

KnowledgeModule

↓

KnowledgeModule[]

↓

ContextObject

↓

PromptObject

↓

Markdown Prompt

↓

Respuesta LLM
```

Cada transformación incrementa el nivel de abstracción.

El Runtime nunca vuelve a depender del formato anterior.

Esta estrategia minimiza el acoplamiento entre componentes.

---

# 5.112 Matriz de Responsabilidades

| Componente | Entrada | Salida | Responsabilidad |
|------------|----------|---------|-----------------|
| KnowledgeEngine | Proyecto | KnowledgeModule[] | Cargar conocimiento |
| KnowledgeResolver | KnowledgeModule[] | KnowledgeModule[] | Seleccionar módulos |
| ContextCompressor | KnowledgeModule[] | KnowledgeModule[] | Reducir contexto |
| ContextEngine | KnowledgeModule[] | ContextObject | Construir contexto |
| PromptBuilder | ContextObject | PromptObject | Construir modelo de prompt |
| PromptEngine | PromptObject | Markdown + Contrato | Preparar prompt operativo |
| PromptRenderer | PromptObject | Prompt Final | Renderizar Markdown |

---

# 5.113 Responsabilidades que NO Existen

Uno de los hallazgos positivos de la auditoría consiste en identificar responsabilidades que deliberadamente no aparecen mezcladas.

Ningún componente:

- llama directamente a OpenAI;
- consulta Internet;
- realiza búsquedas web;
- resume contenido mediante IA;
- modifica conocimiento durante el renderizado;
- mezcla lógica editorial con almacenamiento;
- construye prompts mediante concatenaciones dispersas.

Esta ausencia de responsabilidades cruzadas demuestra un buen diseño de separación de capas.

---

# 5.114 Dependencias entre Componentes

Las dependencias observadas son exclusivamente unidireccionales.

```text
KnowledgeEngine

↓

KnowledgeResolver

↓

ContextCompressor

↓

ContextEngine

↓

PromptBuilder

↓

PromptEngine

↓

PromptRenderer
```

No se identificaron:

- ciclos;
- dependencias recursivas;
- llamadas inversas;
- referencias cruzadas entre capas.

Este diseño simplifica la evolución futura del Runtime.

---

# 5.115 Objetos de Dominio Utilizados

Durante todo el flujo únicamente se intercambian objetos bien definidos.

```text
Project

↓

KnowledgeModule

↓

ContextObject

↓

PromptObject

↓

RenderedPrompt

↓

EngineResult
```

El uso consistente de modelos de dominio evita la proliferación de diccionarios arbitrarios y favorece la validación estática del sistema.

---

# 5.116 Cumplimiento de Principios SOLID

## S — Single Responsibility Principle

Cumplimiento: **Excelente**

Cada componente posee una única responsabilidad claramente delimitada.

---

## O — Open/Closed Principle

Cumplimiento: **Muy Alto**

Es posible incorporar:

- nuevos proveedores;
- nuevos renderizadores;
- nuevas estrategias de contexto;
- nuevos formatos de conocimiento;

sin modificar significativamente los componentes existentes.

---

## L — Liskov Substitution Principle

Cumplimiento: **Adecuado**

Los componentes mantienen contratos consistentes mediante `EngineResult` y modelos compartidos.

---

## I — Interface Segregation Principle

Cumplimiento: **Excelente**

Los componentes consumen únicamente las interfaces necesarias para su función.

No existen dependencias innecesarias.

---

## D — Dependency Inversion Principle

Cumplimiento: **Bueno**

La mayor parte de la lógica depende de modelos del dominio y archivos de configuración en lugar de implementaciones concretas.

La arquitectura favorece futuras abstracciones adicionales.

---

# 5.117 Evaluación de Escalabilidad

El diseño observado permite incorporar sin rediseños importantes:

- nuevos proveedores LLM;
- nuevos formatos de Prompt;
- nuevos formatos de Knowledge Modules;
- múltiples idiomas;
- múltiples plataformas;
- perfiles editoriales;
- estrategias híbridas de recuperación;
- presupuestos dinámicos de contexto.

La arquitectura presenta una elevada capacidad de evolución.

---

# 5.118 Riesgos Arquitectónicos Detectados

Durante la auditoría no se identificaron riesgos críticos.

Se observaron únicamente oportunidades de evolución.

## Gestión avanzada de tokens

Actualmente el presupuesto de contexto puede ampliarse mediante estrategias específicas por proveedor.

---

## Recuperación híbrida

La arquitectura podría incorporar recuperación semántica adicional manteniendo intacto el pipeline actual.

---

## Versionado de contratos

Los contratos de validación podrían versionarse para facilitar la coexistencia de diferentes generaciones del Runtime.

---

## Perfilado editorial

Sería posible introducir perfiles específicos para:

- TikTok;
- YouTube;
- Blog;
- Podcast;
- LinkedIn.

sin alterar la arquitectura existente.

---

# 5.119 Fortalezas Arquitectónicas

La auditoría permitió identificar fortalezas especialmente relevantes.

## Separación estricta de responsabilidades

Cada componente posee un propósito claramente definido.

---

## Pipeline determinista

Ante las mismas entradas siempre se obtiene el mismo Prompt.

---

## Compatibilidad Legacy + Runtime

Los componentes soportan simultáneamente ambas arquitecturas.

---

## Externalización de reglas

Las decisiones editoriales y de conocimiento residen principalmente en archivos YAML.

---

## Bajo acoplamiento

Los componentes interactúan mediante modelos del dominio.

---

## Alta mantenibilidad

La modularidad facilita localizar errores y realizar modificaciones futuras.

---

## Excelente trazabilidad

Cada etapa produce metadatos suficientes para reconstruir el proceso completo.

---

## Independencia del proveedor IA

Toda la preparación ocurre antes de invocar cualquier modelo.

---

# 5.120 Cumplimiento de Objetivos del MVP

Con base en la auditoría realizada, el subsistema cumple adecuadamente los objetivos definidos para el MVP.

| Objetivo | Estado |
|----------|--------|
| Carga estructurada de conocimiento | Cumplido |
| Selección automática de módulos | Cumplido |
| Resolución de dependencias | Cumplido |
| Construcción homogénea del contexto | Cumplido |
| Generación estructurada del Prompt | Cumplido |
| Renderización determinista | Cumplido |
| Compatibilidad Legacy + Runtime | Cumplido |
| Integración con ValidatorEngine | Cumplido |
| Persistencia del Prompt | Cumplido |
| Desacoplamiento del proveedor IA | Cumplido |

No se identificó ningún incumplimiento que comprometa el funcionamiento del MVP.

---

# 5.121 Evaluación Global del Subsistema

| Aspecto Evaluado | Resultado |
|------------------|-----------|
| Cohesión | Excelente |
| Acoplamiento | Muy Bajo |
| Modularidad | Excelente |
| Escalabilidad | Alta |
| Mantenibilidad | Muy Alta |
| Reutilización | Alta |
| Determinismo | Excelente |
| Preparado para producción | Sí (MVP) |

---

# 5.122 Conclusiones Generales del Bloque 2

La auditoría del Subsistema **Knowledge → Context → Prompt** confirma que esta constituye una de las áreas con mayor madurez técnica dentro del Runtime de CIPS.

El flujo implementado establece una cadena de transformación completamente determinista que convierte el conocimiento estructurado del proyecto en un Prompt profesional listo para ser procesado por cualquier proveedor de Inteligencia Artificial compatible.

La separación entre carga de conocimiento, resolución, compresión, construcción del contexto, generación del Prompt y renderización final demuestra una aplicación consistente de principios de ingeniería de software como responsabilidad única, bajo acoplamiento, modularidad y configuración externa mediante contratos declarativos.

La utilización de objetos de dominio (`KnowledgeModule`, `ContextObject`, `PromptObject` y `RenderedPrompt`) reduce significativamente la complejidad del sistema y facilita tanto las pruebas como la evolución futura.

Desde la perspectiva del MVP, el subsistema cumple satisfactoriamente con los objetivos funcionales y arquitectónicos esperados. No se identificaron defectos estructurales que comprometan su operación, observándose únicamente oportunidades de mejora orientadas a futuras versiones, como la gestión avanzada de presupuestos de tokens, perfiles editoriales específicos y estrategias híbridas de recuperación de conocimiento.

En conjunto, el diseño auditado proporciona una base sólida, mantenible y extensible para el ecosistema CIPS, permitiendo que la interacción con los modelos de Inteligencia Artificial se realice mediante un proceso controlado, reproducible y completamente gobernado por el propio Runtime, en lugar de depender de lógica distribuida o de instrucciones construidas de manera ad hoc.