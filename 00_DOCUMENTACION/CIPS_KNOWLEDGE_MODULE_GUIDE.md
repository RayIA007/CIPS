<!--
=========================================================
Proyecto : CIPS
Release   : 0.4
Documento : Knowledge Module Author Guide
Versión   : 1.0
Estado    : OFICIAL
=========================================================
-->

# CIPS KNOWLEDGE MODULE GUIDE

## Guía Oficial para la Creación de Knowledge Modules

---

# PROPÓSITO

Esta guía establece las buenas prácticas para diseñar, escribir, revisar y mantener Knowledge Modules dentro del ecosistema CIPS.

Su objetivo es garantizar que todos los módulos sean:

- comprensibles para personas;
- útiles para el Runtime;
- reutilizables;
- mantenibles;
- verificables.

---

# PRINCIPIOS FUNDAMENTALES

Todo Knowledge Module deberá cumplir los siguientes principios.

## 1. Un módulo = Un problema

Cada módulo debe resolver un único problema.

Incorrecto:

• Marketing + SEO + Copywriting

Correcto:

• SEO para YouTube

• Copywriting para TikTok

• Storytelling para Shorts

---

## 2. Pensar primero en reutilización

Nunca escribir un módulo para un único proyecto.

Pregúntate siempre:

> ¿Este módulo podrá reutilizarse dentro de dos años?

Si la respuesta es "no", probablemente está demasiado acoplado.

---

## 3. Escribir para dos consumidores

Todo módulo será leído por:

- Personas.
- Runtime.

Cada uno necesita información distinta.

Nunca mezclar ambas.

---

# BUENAS PRÁCTICAS

## Utilizar lenguaje preciso

Preferir:

✔️ "Debe"

✔️ "No debe"

✔️ "Siempre"

✔️ "Nunca"

Evitar:

✘ "Quizá"

✘ "Tal vez"

✘ "Sería conveniente"

---

## Escribir reglas pequeñas

Incorrecto:

Una regla de veinte líneas.

Correcto:

Cinco reglas de cuatro líneas.

---

## Evitar duplicidad

Antes de crear un módulo nuevo:

Buscar si el conocimiento ya existe.

Si existe:

Actualizarlo.

No duplicarlo.

---

## Declarar dependencias

Cuando un módulo necesite otro:

Declararlo explícitamente.

Ejemplo:

DEPENDENCIES

- KM-004

- KM-011

---

## Mantener independencia

Las dependencias amplían información.

Nunca deben impedir comprender el módulo principal.

---

# CÓMO ESCRIBIR LA SECCIÓN RUNTIME KNOWLEDGE

La sección Runtime deberá ser:

- breve;
- estructurada;
- determinista;
- libre de narrativa.

Incorrecto:

"Generalmente podría utilizarse..."

Correcto:

"El Runtime deberá..."

---

# CHECKLIST DEL AUTOR

Antes de publicar un módulo verificar:

- [ ] Tiene un único objetivo.
- [ ] Es reutilizable.
- [ ] Contiene Metadata.
- [ ] Contiene Human Knowledge.
- [ ] Contiene Runtime Knowledge.
- [ ] Tiene Dependencies.
- [ ] Tiene Tags.
- [ ] Tiene Keywords.
- [ ] Tiene Confidence.
- [ ] Tiene Priority.
- [ ] Fue revisado.

---

# CHECKLIST DEL REVISOR

Antes de aprobar un módulo verificar:

- [ ] No existe duplicidad.
- [ ] El contenido es correcto.
- [ ] Las reglas son consistentes.
- [ ] Las Keywords son útiles.
- [ ] Las Tags son coherentes.
- [ ] La prioridad está justificada.
- [ ] La confianza corresponde a la evidencia.
- [ ] El módulo cumple la especificación oficial.

---

# EVOLUCIÓN DEL CONOCIMIENTO

Los módulos podrán evolucionar mediante nuevas versiones.

Ejemplo:

v1.0

↓

v1.1

↓

v2.0

Toda modificación importante deberá reflejarse en el CHANGELOG.

Nunca sobrescribir conocimiento sin registrar el cambio.

---

# REGLA DE ORO

El Runtime debe poder utilizar un Knowledge Module sin necesidad de interpretar intención humana.

Toda información crítica deberá encontrarse estructurada dentro de la sección RUNTIME KNOWLEDGE.

---

# CONCLUSIÓN

La calidad del Runtime dependerá directamente de la calidad de sus Knowledge Modules.

Un Runtime inteligente comienza con conocimiento bien estructurado.

---

# FIN DEL DOCUMENTO