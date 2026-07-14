<!--
=========================================================
Proyecto : CIPS
Release   : 0.4
Sprint    : Knowledge System
Documento : Knowledge Module Specification
Versión   : 1.0
Estado    : OFICIAL
=========================================================
-->

# CIPS KNOWLEDGE MODULE SPECIFICATION

---

# PROPÓSITO

Este documento define la especificación oficial de un Knowledge Module dentro del ecosistema CIPS.

Todo módulo de conocimiento deberá seguir esta estructura para garantizar compatibilidad con el Runtime presente y futuro.

---

# OBJETIVOS

Los Knowledge Modules deberán servir simultáneamente a dos consumidores diferentes:

• Personas.

• Runtime.

Por lo tanto, cada módulo deberá separar claramente el conocimiento explicativo del conocimiento operativo.

---

# PRINCIPIOS

Todo Knowledge Module deberá cumplir los siguientes principios.

## 1. Responsabilidad Única

Cada módulo deberá resolver un único tema.

No deberá mezclar múltiples dominios.

---

## 2. Modularidad

Cada módulo deberá poder reutilizarse por distintos proyectos.

Nunca deberá contener información específica de un proyecto.

---

## 3. Independencia

Un módulo deberá ser comprensible por sí mismo.

Las dependencias únicamente ampliarán información.

Nunca deberán ser obligatorias para comprender el objetivo principal.

---

## 4. Versionado

Todo módulo deberá indicar claramente su versión.

Las modificaciones importantes incrementarán la versión correspondiente.

---

## 5. Compatibilidad

El Runtime únicamente consumirá la sección RUNTIME KNOWLEDGE.

Las secciones HUMAN KNOWLEDGE estarán destinadas exclusivamente a consulta humana.

---

# ESTRUCTURA OFICIAL

Todo Knowledge Module deberá dividirse en dos bloques.

```text
HUMAN KNOWLEDGE

↓

RUNTIME KNOWLEDGE
```

Nunca deberán mezclarse.

---

# HUMAN KNOWLEDGE

Destinado al aprendizaje humano.

Podrá contener:

- explicación;
- contexto;
- fundamentos;
- ejemplos;
- referencias;
- historia;
- notas.

El Runtime ignorará completamente esta sección.

---

# RUNTIME KNOWLEDGE

Destinado exclusivamente al Runtime.

Esta sección deberá contener información estructurada y fácilmente procesable.

Nunca deberá escribirse como ensayo.

Su objetivo es proporcionar instrucciones operativas.

---

# REGLA DE ORO

El Runtime nunca interpretará intención.

El Runtime únicamente consumirá estructuras oficialmente definidas.

Por esta razón, la información crítica deberá encontrarse dentro del bloque RUNTIME KNOWLEDGE.

---

# CICLO DE VIDA

Todo Knowledge Module seguirá el siguiente ciclo:

```text
Creación

↓

Revisión

↓

Validación

↓

Publicación

↓

Versionado

↓

Deprecación (si aplica)
```

---

# COMPATIBILIDAD FUTURA

La estructura definida en este documento permitirá evolucionar el Runtime sin modificar los módulos existentes.

Los futuros Engines deberán mantener compatibilidad con esta especificación.

---

# ESTADO

Esta especificación constituye el estándar oficial para todos los Knowledge Modules del proyecto CIPS.

**FIN DEL DOCUMENTO**