---
document:
  id: FAO-OPS-003
  title: Automatización Editorial Verificable
  version: 1.0.0
  status: IMPLEMENTED
  classification: Production System Contract
  owner: ConsejoIA_V5 Architecture
  repository: ConsejoIA_V5
---

# 1. Propósito

Esta especificación define `FAO.3 — Automatización editorial verificable`.
Amplía la ruta iniciada por `CIPS/run.py` para que un workspace fresco creado
por FAO.2 produzca, mediante el proveedor LLM configurado, investigación,
verificación, guion, storyboard, SEO, paquete de publicación y narración
textual completos. El modo manual se conserva únicamente como fallback
explícito y reanudable.

FAO.3 no deriva `ProductionManifest`, no crea consultas de activos, no conecta
la aceptación PM9, no genera multimedia, no consume créditos de render y no
publica. Esas fronteras permanecen reservadas para FAO.4 y FAO.5.

# 2. Ruta oficial

```text
CIPS/run.py
→ MenuController.new_project()
→ ProjectManager.create_project(...)
→ PipelineEngine.execute(project_path)
→ contexto CORE + operational_request.json + entregables aprobados previos
→ PromptEngine + proveedor LLM configurado
→ ValidatorEngine estructural
→ EditorialValidatorEngine semántico/factual-trazable
→ MemoryEngine + transición reanudable
```

El bucle existente de `Nuevo Proyecto` continúa invocando `PipelineEngine`.
`narracion` deja de clasificarse como fase multimedia: se genera como texto
pronunciable mediante el mismo contrato LLM y la producción física comienza en
`voz`. Antes de entrar a la ruta multimedia heredada, el menú exige la presencia
de `state/editorial_package.json`.

# 3. Contexto acumulativo

`EditorialContextEngine` se ejecuta después de `ContextEngine` y antes de
`PromptEngine`. Para un proyecto FAO:

1. valida `operational_request.json` y `publication_performed: false`;
2. incorpora tema, plataforma, duración, audiencia, estilo y Free Tier;
3. carga únicamente los artefactos canónicos requeridos por el Stage;
4. rechaza prerequisitos inexistentes, vacíos o con marcadores sin resolver;
5. añade ruta relativa y SHA-256 de cada entrada al contexto;
6. conserva proyectos heredados sin `operational_request.json` bajo el
   comportamiento anterior.

| Stage | Entradas editoriales aprobadas |
|---|---|
| `investigacion` | solicitud operativa |
| `verificacion` | investigación |
| `guion` | investigación y verificación |
| `storyboard` | verificación y guion |
| `seo` | verificación y guion |
| `publicacion` | verificación, guion y SEO |
| `narracion` | verificación, guion y storyboard |

# 4. Contrato de evidencia

## 4.1 Investigación

- identifica afirmaciones como `[A1]`, `[A2]`, ...;
- declara al menos dos fuentes independientes como `[F1]`, `[F2]`, ...;
- cada fuente incluye título, organización y URL `http/https` completa;
- relaciona cada afirmación con una o más fuentes declaradas;
- no permite referencias a fuentes inexistentes.

## 4.2 Verificación

- decide todas las afirmaciones investigadas;
- sólo admite `APROBADA`, `RECHAZADA` o `INCIERTA`;
- exige al menos una fuente declarada por decisión;
- bloquea IDs de afirmaciones o fuentes inventados;
- exige al menos una afirmación aprobada para continuar.

## 4.3 Guion y storyboard

- sólo pueden citar afirmaciones aprobadas;
- el guion conserva una sección de trazabilidad separada;
- cada escena declara Duración, Visual, Locución y Evidencia;
- la suma física declarada de escenas coincide exactamente con
  `duration_seconds`.

## 4.4 SEO, publicación y narración

- SEO y publicación deben conservar relación semántica con el guion validado;
- el paquete declara literalmente `publication_performed: false` y
  `authorization_required: true`;
- la narración es texto plano sin Markdown, URL ni IDs de evidencia;
- su conteo de palabras debe caber dentro de un rango de locución derivado de
  la duración solicitada;
- la narración conserva hechos aprobados y coherencia con guion/storyboard.

# 5. Alcance de la validación factual

El Stage `verificacion`, ejecutado mediante el proveedor LLM configurado, actúa
como adjudicador editorial sobre las afirmaciones y fuentes de investigación.
El gate determinista posterior comprueba que esa adjudicación sea completa,
que no introduzca IDs nuevos y que todos los entregables posteriores utilicen
únicamente afirmaciones aprobadas.

FAO.3 valida la forma y trazabilidad de las URL declaradas, pero no descarga ni
resuelve por red el contenido remoto. La comprobación independiente de
disponibilidad, vigencia y concordancia física de cada fuente pertenece al gate
de calidad factual reforzado previsto para FAO.6. Esta separación evita
presentar una comprobación sintáctica como evidencia física de red.

# 6. Persistencia y trazabilidad

Cada Stage aprobado actualiza atómicamente:

`state/editorial_evidence.json`

```json
{
  "schema_name": "cips.fao.editorial_evidence",
  "schema_version": "1.0",
  "project_id": "PROYECTO_NNNN",
  "operational_request_sha256": "sha256",
  "publication_performed": false,
  "stages": {
    "investigacion": {
      "artifact_path": "research/01_INVESTIGACION.md",
      "artifact_sha256": "sha256",
      "prompt_sha256": "sha256",
      "provider": "configured-provider",
      "model": "configured-model",
      "manual_fallback": false,
      "source_ids": ["F1", "F2"],
      "claim_ids": ["A1", "A2"],
      "semantic_validation": true,
      "factual_traceability_validation": true,
      "publication_performed": false
    }
  }
}
```

Una repetición con contenido idéntico conserva el mismo registro lógico y no
duplica Stages. Los seis artefactos Markdown validados se sincronizan además
con las rutas raíz heredadas. La narración conserva como autoridad canónica
`narration/narration.txt`.

Cuando los siete Stages están presentes, sus hashes coinciden con el ledger y
ninguno contiene marcadores sin resolver, se persiste atómicamente:

`state/editorial_package.json`

El paquete registra `editorial_complete`, siete artefactos, hashes, ruta/hash
del ledger, validación semántica/factual-trazable, Free Tier y publicación
desactivada.

# 7. Fallback manual y recuperación

La ruta normal utiliza el proveedor activo resuelto por `LLMAdapter`. El
proveedor manual no genera texto ni copia respuestas automáticamente. Cuando se
selecciona explícitamente y no existe respuesta:

- devuelve `requires_user_action: true`;
- el menú pausa sin marcar el Stage como aprobado;
- conserva prompt, workspace y checkpoint;
- `Continuar Proyecto` reanuda desde el Stage persistido;
- el contenido manual pasa por los mismos validadores y evidencia que el
  contenido automático.

No existe fallback silencioso que haga pasar una respuesta faltante como
entregable completo.

# 8. Invariantes

1. `CIPS/run.py` sigue siendo la entrada principal.
2. `operational_request.json` es la autoridad de los cinco campos FAO.
3. Los entregables canónicos permanecen provider-neutral.
4. `publication_performed` permanece siempre en `false`.
5. FAO.3 no llama proveedores multimedia, PM9 ni redes sociales.
6. No se ejecuta render y no se solicita autorización de créditos.
7. El texto de narración no contiene IDs que puedan ser pronunciados.
8. Los proyectos heredados sin solicitud FAO conservan compatibilidad.
9. FAO.4, FAO.5 y PM10 permanecen fuera del alcance.

# 9. Validación automatizada

`08_SCRIPTS/tests/test_fao_editorial_automation.py` cubre:

- contexto con solicitud y prerequisitos aprobados;
- bloqueo de investigación sin dos URL trazables;
- bloqueo de referencias de fuente inexistentes;
- bloqueo de duraciones de storyboard incoherentes;
- fallback manual explícito;
- compatibilidad de proyectos heredados;
- cadena completa con proveedor inyectado y sin red;
- ledger y paquete editorial con siete artefactos;
- idempotencia de evidencia para contenido idéntico;
- ausencia de archivos Markdown iniciales con `Pendiente`.

La aceptación requiere además las pruebas FAO.1–FAO.3, la regresión completa de
`08_SCRIPTS/test_f2_smoke.py` más `08_SCRIPTS/tests` y `git diff --check`.
