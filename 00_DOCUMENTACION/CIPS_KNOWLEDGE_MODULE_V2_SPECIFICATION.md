<!--
=========================================================
Proyecto : CIPS
Release  : 0.4
Documento: Knowledge Module v2 Specification
Versión  : 1.0
Estado   : OFICIAL
=========================================================
-->

# CIPS KNOWLEDGE MODULE V2 SPECIFICATION

---

# PROPÓSITO

Este documento define la estructura oficial v2 para los Knowledge Modules de CIPS.

El objetivo es separar claramente el conocimiento destinado a personas del conocimiento destinado al Runtime.

---

# PRINCIPIO FUNDAMENTAL

Un Knowledge Module v2 será una carpeta.

No un único archivo Markdown.

---

# ESTRUCTURA OFICIAL

Todo Knowledge Module v2 utilizará la siguiente estructura.

```text
KM-XXX_NOMBRE/
│
├── METADATA.yaml
├── HUMAN.md
├── RUNTIME.yaml
└── CHANGELOG.md