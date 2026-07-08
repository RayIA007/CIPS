<!--
=========================================================
Proyecto : CIPS
Release   : 0.2
Sprint    : Knowledge Sprint 002
Build     : CIF-009
Archivo   : KM-007_CIPS_CONTEXT_ENGINEERING.md
Ubicación : 09_KNOWLEDGE/00_CORE/
Versión   : 1.0
Estado    : RELEASE
=========================================================
-->

# KM-007 — CIPS CONTEXT ENGINEERING

## Knowledge Module

---

# METADATOS

| Campo | Valor |
|--------|-------|
| ID | KM-007 |
| Categoría | CORE |
| Tipo | Context Engineering |
| Prioridad | Crítica |
| Reutilizable | Sí |
| Dependencias | KM-000 al KM-006 |

---

# PROPÓSITO

Definir la metodología oficial mediante la cual CIPS construirá el contexto enviado a los modelos de Inteligencia Artificial.

El objetivo consiste en proporcionar únicamente el conocimiento indispensable para resolver correctamente una tarea, minimizando el consumo de contexto y maximizando la calidad del resultado.

---

# DEFINICIÓN

En CIPS, el **Context Engineering** es la disciplina encargada de seleccionar, organizar y ensamblar módulos de conocimiento para producir un contexto óptimo antes de construir un prompt.

El contexto representa el verdadero activo operativo del sistema.

El prompt es únicamente su representación temporal.

---

# OBJETIVOS

Todo proceso de Context Engineering deberá perseguir simultáneamente los siguientes objetivos.

- Reducir tokens.
- Incrementar precisión.
- Evitar redundancias.
- Mantener coherencia.
- Maximizar reutilización.
- Facilitar mantenimiento.
- Mejorar velocidad de respuesta.

---

# PRINCIPIOS

## Principio de Mínimo Contexto

Sólo deberá cargarse el conocimiento estrictamente necesario.

Todo conocimiento innecesario deberá excluirse.

---

## Principio de Máxima Relevancia

Cada módulo deberá aportar información directamente relacionada con el objetivo solicitado.

---

## Principio de No Duplicación

Un concepto únicamente podrá aparecer una vez dentro del contexto.

Si varios módulos contienen la misma información, deberá conservarse únicamente la versión oficial.

---

## Principio de Prioridad

El orden de carga del contexto será obligatorio.

Nunca podrá modificarse sin autorización arquitectónica.

---

# ORDEN OFICIAL DE ENSAMBLAJE

Todo contexto deberá construirse respetando la siguiente secuencia.

```
1. KM-000 Identidad

↓

2. Misión

↓

3. Valores

↓

4. Principios de Decisión

↓

5. Política Editorial

↓

6. Política Científica

↓

7. Framework de Calidad

↓

8. Especialistas

↓

9. Etapa

↓

10. Nicho

↓

11. Plataforma

↓

12. Estilo

↓

13. Formato de salida
```

---

# CONTEXTO BASE

Todo proyecto iniciará cargando automáticamente.

- KM-000
- KM-001
- KM-002
- KM-003
- KM-004
- KM-005
- KM-006
- KM-007

Este conjunto constituye el **Core Context** de CIPS.

---

# CONTEXTO DINÁMICO

Después del contexto base, el Knowledge Engine incorporará únicamente los módulos específicos del proyecto.

Ejemplo.

Proyecto:

```
Vitamina D
```

Contexto adicional.

```
Nicho:

Salud

↓

Especialistas:

Investigador Científico

Nutriólogo

Endocrinólogo

↓

Etapa:

Investigación

↓

Plataforma:

YouTube

↓

Formato:

Guion Largo
```

---

# CRITERIOS DE SELECCIÓN

Antes de incorporar un módulo, el Knowledge Engine deberá responder.

- ¿Es necesario?
- ¿Es relevante?
- ¿Ya existe otro módulo equivalente?
- ¿Incrementa la calidad?
- ¿Reduce incertidumbre?

Si alguna respuesta es negativa, el módulo no deberá cargarse.

---

# OPTIMIZACIÓN

El Context Engineering buscará permanentemente.

- eliminar redundancias;
- resumir información repetida;
- reutilizar módulos;
- minimizar longitud;
- maximizar información útil.

---

# REGLAS DE COMPATIBILIDAD

Todo módulo incorporado deberá ser compatible con.

- Constitución.
- Standards.
- Core.
- Especialistas previamente cargados.

Los conflictos deberán resolverse utilizando KM-003_CIPS_DECISION_PRINCIPLES.

---

# VALIDACIÓN DEL CONTEXTO

Antes de construir un prompt, el contexto deberá verificarse.

Checklist.

- ¿Existe identidad?
- ¿Existe misión?
- ¿Existen valores?
- ¿Existe política editorial?
- ¿Existe política científica?
- ¿Existe framework de calidad?
- ¿Existe etapa?
- ¿Existen especialistas?
- ¿Existe nicho?
- ¿Existe formato?

---

# RESULTADO ESPERADO

El resultado del Context Engineering será un objeto estructurado que represente todo el conocimiento necesario para resolver correctamente una tarea.

Ese objeto será la entrada oficial del Prompt Assembly Engine.

---

# ENTRADAS

Este módulo recibe.

- proyecto;
- etapa;
- nicho;
- plataforma;
- objetivo;
- formato.

---

# SALIDAS

Produce.

- contexto optimizado;
- lista de módulos utilizados;
- orden de ensamblaje;
- justificación de selección.

---

# USO DENTRO DEL KNOWLEDGE ENGINE

Este módulo constituye la guía principal del Knowledge Engine.

Toda construcción de contexto deberá respetar las reglas aquí definidas.

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

---

# HISTORIAL

| Versión | Estado | Descripción |
|----------|--------|-------------|
| 1.0 | Release | Primer módulo oficial de Context Engineering |

---

# DECLARACIÓN FINAL

El Context Engineering constituye el mecanismo mediante el cual CIPS transforma una biblioteca de conocimiento en inteligencia operativa.

La calidad del contexto determina directamente la calidad del resultado.

Por ello, el Knowledge Engine deberá considerar este módulo como una referencia permanente para construir contextos precisos, eficientes, reutilizables y alineados con la arquitectura oficial del sistema.

---

**FIN DEL ARCHIVO**