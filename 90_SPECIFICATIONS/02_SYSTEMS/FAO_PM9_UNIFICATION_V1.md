# FAO.5 — Unificación operativa con la cadena PM9

**Estado del contrato:** implementado para FAO.5

**Entrada oficial:** `CIPS/run.py`

**Frontera de salida:** `ready_for_render_authorization`

**Render real:** prohibido en esta subfase

**Publicación:** prohibida

## 1. Objetivo

FAO.5 conecta un proyecto fresco creado por la entrada oficial de CIPS con las
fronteras de producción ya validadas en PM9. La conexión reutiliza los módulos
existentes; no crea un segundo menú, otro CLI ni un pipeline audiovisual
paralelo.

El resultado esperado es una preparación física y auditable que incluya
inventario, assets gratuitos, visuales, narración, música, efectos, subtítulos,
payload y evidencia PM9. El flujo termina antes de cualquier llamada al
proveedor de render y antes de solicitar una decisión F7.

## 2. Topología operativa

```text
CIPS/run.py
→ MenuController.new_project / continue_project_runtime
→ PipelineEngine editorial FAO.3
→ ProductionDerivationEngine FAO.4
→ FAOPM9UnificationEngine FAO.5
→ inventario PM9
→ PM9SourceAssetBuilder
→ ManifestAssetResolver + WikimediaCommonsProvider
→ VisualAssetFulfillmentService
→ FullProductionAcceptance.prepare
→ F3 + subtítulos canónicos + payload + telemetría F8
→ ready_for_render_authorization
```

No se invocan las operaciones PM9 `render` ni `accept`. El pipeline multimedia
heredado continúa disponible únicamente para proyectos heredados que no tengan
`operational_request.json`.

## 3. Entradas obligatorias

El proyecto debe estar confinado dentro de `04_PROYECTOS` y contener:

- `operational_request.json` con schema `cips.fao.operational_request` `1.0`;
- `free_tier_default: true`;
- `publication_performed: false`;
- paquete editorial FAO.3 válido y sus artefactos físicos;
- `production_manifest.json`, `production_acceptance_config.json` y
  `state/production_derivation.json` reproducibles mediante FAO.4.

FAO.5 vuelve a ejecutar la validación FAO.4 antes de usar sus salidas. Una
alteración de los hashes editoriales bloquea la preparación.

## 4. Reutilización de PM9

FAO.5 compone las fronteras existentes:

- `ProductionManifestCompiler` y `CreativeDirectionPlanner` para preservar el
  manifest provider-neutral;
- `PM9SourceAssetBuilder` para Piper, narración, música y efectos locales;
- `ManifestAssetResolver`, `CapabilityResolver` y
  `WikimediaCommonsProvider` para visuales Free Tier;
- `VisualAssetFulfillmentService` para staging, procedencia, licencia y costo;
- `FullProductionAcceptance.prepare` para resolución final, subtítulos,
  adaptación de render, payload y evidencia de preparación;
- `MetadataStore` y los stores especializados de F3 para contenido, hashes y
  sidecars;
- telemetría F8 persistida por la preparación PM9.

El constructor de assets admite en proyectos nuevos una combinación de
`stock_image`, `motion_graphic` y `text_graphic`. Los dos últimos permanecen
renderer-native y no reciben binarios artificiales. Otros tipos físicos deben
resolverse por PM8 y no se sustituyen mediante hardcodes.

## 5. Selección del adaptador

`FAOPM9UnificationEngine` acepta `creatomate` y `json2video` como adaptadores de
preparación. La entrada oficial utiliza el valor compatible `creatomate` en
FAO.5, porque puede compilar directamente gráficos renderer-native. Esta
selección pertenece a la frontera de render y no modifica el dominio editorial
ni introduce campos de proveedor en `production_manifest.json`.

El adaptador sigue siendo sustituible por configuración del motor. Un proyecto
compatible compuesto por assets físicos también puede prepararse para
JSON2Video. Ningún adaptador recibe credenciales ni realiza red durante
`prepare`.

## 6. Subtítulos y conformidad acústica

FAO.5 solicita siempre la construcción y persistencia del SRT canónico desde el
texto aprobado y las duraciones físicas de la narración. La política acústica
de `production_acceptance_config.json` permanece activa por defecto:

- Piper sintetiza la voz local;
- Faster-Whisper `small` actúa como sensor primario;
- Faster-Whisper `medium` adjudica diferencias cuando está configurado;
- el guion no puede reescribirse automáticamente;
- una narración no conforme bloquea la preparación.

El SRT canónico se conserva como evidencia aunque el adaptador preparado use
su propio contrato de captions.

## 7. Gates de seguridad

La preparación se bloquea cuando ocurre cualquiera de estas condiciones:

- el proyecto no proviene de la solicitud operativa FAO;
- Free Tier no está activo;
- `publication_performed` no es `false`;
- existe previamente un resultado de render, aceptación final o MP4 final;
- FAO.4 no puede reproducir y validar sus entradas;
- falta un artefacto físico o su hash no coincide;
- aparece costo de assets distinto de cero;
- existe costo desconocido;
- PM9 reporta bloqueadores o `ready_for_real_render: false`;
- F8 no persiste la telemetría de preparación.

La estimación de créditos del render se calcula y registra, pero no autoriza ni
consume créditos. Una autorización posterior deberá ser humana, nueva,
explícita y cuantificada.

## 8. Evidencia persistida

La salida canónica es:

`state/fao_pm9_unification.json`

Schema:

`cips.fao.pm9_unification` `1.0`

Estado exitoso:

`ready_for_render_authorization`

La evidencia incluye:

- tema, proyecto, manifest, resolución, plan, submission e idempotency key;
- fingerprint de las entradas FAO.4 y del adaptador elegido;
- inventario y conteos de assets;
- hashes, tamaños y rutas POSIX confinadas de cada salida;
- SRT canónico y conformidad acústica;
- costo previo real y costos desconocidos;
- estimación de créditos del render futuro;
- confirmación de persistencia F3 y telemetría F8;
- `f7_review_state: not_started`;
- `paid_provider_called: false`;
- `render_performed: false`;
- `publication_performed: false`.

La evidencia tiene sidecar F3. Una reanudación con el mismo fingerprint verifica
todos los hashes y reutiliza la preparación sin repetir builders, proveedores,
assets ni costos.

## 9. Comportamiento de la entrada oficial

### Nuevo Proyecto

Cuando el pipeline editorial llega a `voz` y existe
`operational_request.json`, `MenuController` ejecuta FAO.5. En caso de éxito:

- actualiza `production.json` a `READY_FOR_RENDER_AUTHORIZATION`;
- agrega el checkpoint `ready_for_render_authorization`;
- muestra proveedor, costo previo, estimación de créditos y ruta de evidencia;
- informa que no hubo render, F7 ni publicación;
- termina la ejecución sin mostrar la revisión de un MP4 inexistente.

### Continuar Proyecto

Un proyecto FAO detenido en un stage multimedia vuelve a la misma frontera
FAO.5. Si la evidencia y sus hashes siguen válidos, la preparación se reutiliza.
El operador selecciona el proyecto por número y no escribe rutas internas.

## 10. Límites de FAO.5

FAO.5 no implementa:

- verificación factual remota reforzada;
- evaluación editorial o visual de calidad integral;
- diagnóstico y remediación avanzada de defectos;
- render real;
- QA físico de un MP4;
- decisión humana F7;
- exportación final F8;
- publicación.

Los gates de calidad, recuperación y diagnóstico pertenecen a FAO.6. El ensayo
controlado y cualquier render autorizado pertenecen a FAO.7. FAO.5 no inicia
ninguna de esas subfases.

## 11. Evidencia mínima de pruebas

Las pruebas focales de FAO.5 deben demostrar:

1. proyecto fresco FAO.4 → preparación PM9 con
   `ready_for_real_render: true`;
2. costo previo real `0.0`, costo desconocido `0` y proveedor pagado no llamado;
3. inventario, catálogo, fulfillment, subtítulos, payload, F3 y F8 persistidos;
4. ausencia de render, aceptación F7 y publicación;
5. reanudación idempotente sin nuevas llamadas;
6. bloqueo de una solicitud que desactive Free Tier;
7. bloqueo de proyectos que ya contengan una salida de render;
8. enrutamiento de `Nuevo Proyecto` y `Continuar Proyecto` desde el menú oficial
   hacia el mismo puente PM9.
