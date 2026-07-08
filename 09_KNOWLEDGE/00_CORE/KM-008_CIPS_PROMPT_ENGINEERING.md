<!--
=========================================================
Proyecto : CIPS
Release   : 0.2
Sprint    : Knowledge Sprint 002
Build     : CIF-010
Archivo   : KM-008_CIPS_PROMPT_ENGINEERING.md
Ubicación : 09_KNOWLEDGE/00_CORE/
Versión   : 1.0
Estado    : RELEASE
=========================================================
-->

# KM-008 — CIPS PROMPT ENGINEERING

## Knowledge Module

---

# METADATOS

| Campo | Valor |
|--------|-------|
| ID | KM-008 |
| Categoría | CORE |
| Tipo | Prompt Engineering |
| Prioridad | Crítica |
| Reutilizable | Sí |
| Dependencias | KM-000 al KM-007 |

---

# PROPÓSITO

Definir la metodología oficial mediante la cual CIPS construirá prompts de alta calidad a partir del contexto generado por el Knowledge Engine.

Este módulo no contiene prompts específicos.

Define únicamente las reglas para construirlos.

---

# DEFINICIÓN

En CIPS un prompt representa un objeto temporal.

Su finalidad consiste exclusivamente en comunicar al modelo de Inteligencia Artificial el contexto necesario para resolver una tarea.

El prompt nunca constituye conocimiento permanente.

---

# OBJETIVOS

Todo Prompt Assembly deberá perseguir simultáneamente.

- máxima claridad;
- mínimo consumo de contexto;
- máxima precisión;
- instrucciones no ambiguas;
- estructura consistente;
- independencia del modelo de IA.

---

# PRINCIPIOS

## Principio de Separación

El conocimiento pertenece al Knowledge Library.

El prompt únicamente organiza dicho conocimiento.

---

## Principio de Temporalidad

Todo prompt podrá eliminarse después de utilizarse.

El conocimiento permanecerá siempre almacenado dentro del CIF.

---

## Principio de Claridad

Las instrucciones deberán ser:

- directas;
- específicas;
- medibles;
- verificables.

Nunca ambiguas.

---

## Principio de Modularidad

El prompt se construirá ensamblando módulos.

Nunca mediante grandes bloques de texto escritos manualmente.

---

## Principio de Compatibilidad

El Prompt Assembly deberá generar prompts compatibles con distintos modelos de IA.

Nunca dependerá de un único proveedor.

---

# ESTRUCTURA OFICIAL

Todo prompt construido por CIPS seguirá el siguiente orden.

```
Identidad

↓

Objetivo

↓

Contexto

↓

Especialistas

↓

Restricciones

↓

Proceso esperado

↓

Formato de salida

↓

Criterios de calidad
```

---

# IDENTIDAD

El Prompt Assembly deberá comenzar indicando la identidad profesional requerida.

Ejemplo.

```
Actúa como un Consejo de Especialistas...
```

La identidad nunca contendrá conocimiento técnico.

---

# OBJETIVO

El objetivo deberá responder únicamente.

¿Qué debe conseguir el modelo?

Nunca.

¿Cómo debe pensar?

Ese comportamiento pertenece al contexto.

---

# CONTEXTO

El contexto será generado automáticamente por el Knowledge Engine.

Nunca se escribirá manualmente.

---

# ESPECIALISTAS

El Prompt Assembly incorporará únicamente los especialistas seleccionados por el Knowledge Engine.

Nunca especialistas innecesarios.

---

# RESTRICCIONES

Toda tarea deberá indicar claramente.

- qué puede hacerse;
- qué no debe hacerse;
- límites de actuación;
- prioridades.

---

# PROCESO ESPERADO

Cuando sea necesario podrá describirse un procedimiento.

Ejemplo.

```
Analizar

↓

Comparar

↓

Verificar

↓

Sintetizar

↓

Responder
```

---

# FORMATO DE SALIDA

Todo prompt deberá especificar claramente.

- Markdown;
- JSON;
- Tabla;
- SOP;
- Checklist;
- Guion;
- Storyboard;
- Informe.

Nunca dejar el formato implícito.

---

# CRITERIOS DE CALIDAD

Todo prompt deberá solicitar explícitamente.

- claridad;
- precisión;
- consistencia;
- evidencia;
- estructura;
- verificabilidad.

---

# PROMPTS PROHIBIDOS

CIPS evitará.

- instrucciones ambiguas;
- múltiples objetivos mezclados;
- especialistas redundantes;
- restricciones contradictorias;
- formatos indefinidos.

---

# PROMPT MÍNIMO

Todo prompt deberá responder.

- ¿Quién eres?

- ¿Qué debes hacer?

- ¿Con qué conocimiento cuentas?

- ¿Qué restricciones existen?

- ¿Qué formato debe producirse?

---

# PROMPT ÓPTIMO

Además del Prompt Mínimo deberá incluir.

- criterios de calidad;
- prioridades;
- validaciones;
- objetivos editoriales;
- nivel técnico.

---

# RESPONSABILIDADES

## Knowledge Engine

Seleccionar conocimiento.

---

## Prompt Assembly Engine

Construir el prompt.

---

## Modelo IA

Resolver la tarea.

---

## Validator

Evaluar el resultado.

Cada componente posee una responsabilidad exclusiva.

---

# ENTRADAS

Este módulo recibe.

- contexto ensamblado;
- objetivo;
- formato de salida;
- modelo IA.

---

# SALIDAS

Produce.

- prompt completo;
- estructura validada;
- prompt optimizado.

---

# USO DENTRO DEL KNOWLEDGE ENGINE

Este módulo deberá utilizarse inmediatamente antes del Prompt Assembly Engine.

Representa el puente entre el conocimiento estructurado y la comunicación con el modelo de IA.

---

# DEPENDENCIAS

Depende de.

- KM-000_CIPS_IDENTITY.md
- KM-001_CIPS_MISSION_AND_VISION.md
- KM-002_CIPS_VALUES.md
- KM-003_CIPS_DECISION_PRINCIPLES.md
- KM-004_CIPS_EDITORIAL_POLICY.md
- KM-005_CIPS_SCIENTIFIC_POLICY.md
- KM-006_CIPS_QUALITY_FRAMEWORK.md
- KM-007_CIPS_CONTEXT_ENGINEERING.md

---

# HISTORIAL

| Versión | Estado | Descripción |
|----------|--------|-------------|
| 1.0 | Release | Primer módulo oficial de Prompt Engineering |

---

# DECLARACIÓN FINAL

El Prompt Engineering no constituye el núcleo de CIPS.

El núcleo es el conocimiento.

Los prompts son únicamente la representación temporal del conocimiento seleccionado por el Knowledge Engine.

Al separar permanentemente el conocimiento de los prompts, CIPS garantiza independencia tecnológica, reutilización, mantenibilidad y escalabilidad, permitiendo que cualquier modelo de Inteligencia Artificial pueda utilizar el mismo patrimonio intelectual sin modificar la arquitectura del sistema.

---

**FIN DEL ARCHIVO**