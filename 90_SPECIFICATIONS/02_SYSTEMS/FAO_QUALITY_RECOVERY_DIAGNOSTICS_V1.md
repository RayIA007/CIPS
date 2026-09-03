# FAO.6 — Calidad, recuperación y diagnóstico V1

## 1. Propósito

FAO.6 añade una frontera obligatoria entre la preparación FAO.5 y cualquier
solicitud futura de render. Su objetivo es impedir que un proyecto llegue a la
autorización de gasto sólo porque sus archivos existen: las fuentes, el
contenido, los visuales, la narración y la entrega técnica también deben tener
evidencia física vigente.

FAO.6 no renderiza, no inicia F7, no consume créditos y no publica.

## 2. Punto de integración

La entrada oficial sigue siendo `CIPS/run.py`:

```text
CIPS/run.py
→ MenuController
→ FAOPM9UnificationEngine.prepare (FAO.5)
→ FAOQualityRecoveryEngine.evaluate (FAO.6)
→ ready_for_render_authorization o quality_gate_blocked
```

No se crea un CLI ni un menú paralelo. `Nuevo Proyecto` y `Continuar Proyecto`
usan la misma frontera.

## 3. Entrada obligatoria

FAO.6 sólo acepta un proyecto directamente contenido en `04_PROYECTOS` que ya
tenga una evidencia `state/fao_pm9_unification.json` FAO.5 válida, con estado
`ready_for_render_authorization` y `ready_for_real_render: true`.

Antes de evaluar calidad se comprueban todas las referencias físicas declaradas
por FAO.5:

- ruta confinada dentro del proyecto;
- archivo presente y no vacío;
- tamaño exacto;
- SHA-256 exacto;
- schema compatible del manifest, configuración, catálogo y preparación.

Una inconsistencia en esta frontera se considera un error de integridad, no una
autorización implícita para regenerar, renderizar o publicar.

## 4. Gates obligatorios

### 4.1 Gate factual físico

- Extrae las fuentes `[F#]` y las relaciones `[A#] → [F#]` ya aprobadas por
  FAO.3.
- Exige al menos dos fuentes independientes y HTTPS.
- Rechaza localhost, credenciales en URL y direcciones IP no públicas.
- Descarga de forma acotada el contenido textual HTML/plain.
- Registra URL final, estado HTTP, tipo, tamaño, SHA-256, ETag y Last-Modified
  cuando estén disponibles.
- Exige texto suficiente y concordancia léxica mínima con el título, el tema y
  las afirmaciones enlazadas.
- Bloquea fuentes caídas, redirecciones inseguras, páginas vacías o contenido
  físicamente ajeno al tema.

Este gate prueba disponibilidad, vigencia de acceso, legibilidad, concordancia
temática y unión física de citas. No convierte una coincidencia léxica en una
certeza epistemológica ni permite promover afirmaciones `RECHAZADA` o
`INCIERTA`; la adjudicación editorial previa continúa siendo obligatoria.

### 4.2 Gate editorial

- Conserva la alineación del tema entre solicitud, investigación y narración.
- Impide que guion o storyboard utilicen afirmaciones no aprobadas.
- Comprueba un ritmo pronunciable de 75 a 210 palabras por minuto.
- Bloquea repetición narrativa excesiva.
- Exige intención visual específica por escena.
- Tolera una diferencia máxima de 15 % entre duración solicitada y duración
  estimada del manifest, sin alterar automáticamente el guion.

### 4.3 Gate visual

- Requiere exactamente el asset físico correspondiente a cada escena no
  renderer-native.
- Recalcula SHA-256 y firma/dimensiones físicas.
- Para imágenes exige al menos 640 × 360.
- Comprueba que la consulta usada coincide con la permitida y que el título,
  atribución o URL del asset seleccionado conserva términos reconocibles de la
  intención visual.
- Mantiene `motion_graphic` y `text_graphic` como assets renderer-native, pero
  exige un brief específico; no fabrica binarios ficticios.

El reporte de fulfillment conserva ahora `selected_title` para que esta decisión
sea auditable y no dependa sólo de la consulta enviada al buscador.

### 4.4 Gate acústico

- Reutiliza `inspect_narration_conformance`; no vuelve a ejecutar ASR.
- Comprueba policy, manifest, escenas, texto canónico y SHA-256 de cada audio.
- Exige que FAO.5 haya declarado conformidad requerida y aprobada cuando la
  configuración habilita Faster-Whisper.
- Bloquea evidencia faltante, obsoleta, rechazada o acústicamente divergente.

### 4.5 Gate técnico y de entrega pública

- Revalida que la preparación PM9 siga lista y sin blockers.
- Exige 1080 × 1920, 9:16, 30 FPS y duración dentro de 15 % de la solicitud.
- Verifica que el payload de render sea un objeto JSON no vacío.
- Conserva costo real cero, costos conocidos, F7 `not_started`, render false y
  publicación false.
- Reutiliza `verify_catalog_delivery` para descargar cada URL que recibiría el
  renderizador y comparar sus bytes exactos contra el asset local.

Una URL pública inexistente o con bytes distintos bloquea la autorización. La
existencia del archivo local no sustituye esta prueba.

## 5. Evidencia y observabilidad

El resultado canónico es:

`state/fao_quality_recovery.json`

Se persiste con sidecar F3 y contiene:

- fingerprint de todas las entradas físicas;
- decisión y checks de los cinco gates;
- códigos de bloqueo estables;
- diagnóstico y pasos de recuperación para el operador;
- número de llamadas de red a fuentes y entregas;
- ventana de vigencia de 24 horas;
- costo cero, render false, F7 no iniciado y publicación false.

FAO.6 registra además un evento F8 idempotente de aprobación o bloqueo bajo el
mismo fingerprint.

## 6. Idempotencia y reanudación

El fingerprint incluye los archivos editoriales, manifest, configuración,
catálogo, fulfillment, preparación, evidencia acústica, payload y cada asset
físico.

- Una decisión aprobada y vigente se reutiliza sin repetir proveedores,
  adquisición, síntesis, ASR ni llamadas HTTP.
- Un bloqueo no transitorio se reutiliza sin repetir llamadas mientras las
  entradas no cambien.
- Un bloqueo por fuente o entrega pública temporalmente inaccesible puede
  reintentarse desde `Continuar Proyecto`.
- La evidencia aprobada expira a las 24 horas para no confundir idempotencia con
  vigencia indefinida de recursos remotos.

## 7. Diagnóstico del operador

La interfaz muestra:

- que el render fue bloqueado antes de gastar;
- los códigos exactos del problema;
- la ruta de evidencia;
- si el reintento es seguro;
- pasos concretos en lenguaje no técnico.

El checkpoint queda en `quality_gate_blocked`. Sólo después de aprobar los cinco
gates se conserva `READY_FOR_RENDER_AUTHORIZATION`.

## 8. Códigos principales

| Familia | Ejemplos |
|---|---|
| Factual | `factual_source_unavailable`, `factual_source_not_concordant`, `factual_claim_not_physically_supported` |
| Editorial | `editorial_topic_drift`, `editorial_repetition`, `editorial_spoken_duration_out_of_range` |
| Visual | `visual_asset_quality_failed`, `visual_renderer_native_brief_incomplete` |
| Acústica | `narration_conformance_missing_or_stale`, `acoustic_evidence_missing_or_rejected` |
| Técnica | `technical_preparation_not_ready`, `technical_public_delivery_unavailable`, `technical_safety_boundary_breached` |

## 9. Invariantes de seguridad

- Free Tier permanece como política predeterminada.
- Ningún gate llama a un proveedor pagado.
- Ningún gate genera imágenes o video.
- Ningún gate reescribe el texto aprobado.
- Ningún gate reemplaza F7.
- Ningún gate publica.
- Una autorización de gasto anterior no puede reutilizarse.
- `ProductionManifest` permanece provider-neutral.

## 10. Criterios de aceptación FAO.6

1. Un proyecto íntegro con fuentes y entregas simuladas válidas aprueba los
   cinco gates.
2. Reanudar ese proyecto reutiliza la evidencia sin nuevas llamadas ni cambios
   de bytes.
3. Una fuente inaccesible bloquea y ofrece recuperación reintentable.
4. Un visual corrupto bloquea y una reanudación idéntica reutiliza el diagnóstico.
5. Evidencia acústica obsoleta bloquea sin ejecutar ASR.
6. Bytes remotos distintos a los locales bloquean antes del render.
7. Narración repetida o fuera de duración bloquea el gate editorial.
8. La regresión FAO.1–FAO.6, la regresión completa y `git diff --check` deben
   pasar antes de entregar el ZIP.
