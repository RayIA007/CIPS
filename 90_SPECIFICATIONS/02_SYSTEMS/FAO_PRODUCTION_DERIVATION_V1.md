# FAO.4 — Derivación automática de producción V1

## 1. Estado y alcance

FAO.4 convierte el paquete editorial verificable de FAO.3 en insumos de
producción provider-neutral sin pedir al operador que escriba o edite JSON.

Esta subfase:

- reutiliza `ProductionManifestCompiler` (PM2);
- reutiliza `CreativeDirectionPlanner` (PM3);
- genera y valida `production_manifest.json`;
- deriva dirección creativa, tipos de activos y consultas por escena;
- genera y valida `production_acceptance_config.json` compatible con la
  frontera PM9 existente;
- persiste `state/production_derivation.json` como evidencia reproducible;
- se ejecuta al validar `narracion`, antes de avanzar a `voz`;
- no conecta todavía la entrada oficial con la ejecución integral PM9.

La unificación tema → preparación PM9 permanece reservada para FAO.5.

## 2. Entradas autoritativas

FAO.4 requiere dentro del proyecto:

1. `operational_request.json` con schema
   `cips.fao.operational_request` versión `1.0`;
2. `state/editorial_package.json` con schema
   `cips.fao.editorial_package` versión `1.0` y estado
   `editorial_complete`;
3. `state/editorial_evidence.json` cuyo SHA-256 coincida con el declarado;
4. los siete entregables editoriales físicos de FAO.3, en orden:
   investigación, verificación, guion, storyboard, SEO, publicación y
   narración;
5. coincidencia SHA-256 entre cada entregable físico y el paquete FAO.3;
6. `semantic_validation: true`,
   `factual_traceability_validation: true`, cero placeholders y
   `publication_performed: false`.

Una discrepancia bloquea la derivación. El Stage no avanza desde `narracion`.

## 3. Flujo determinista

```text
operational_request.json
+ state/editorial_package.json
+ siete artefactos editoriales verificados
→ validación física de schemas, pertenencia y SHA-256
→ ProductionManifestCompiler
→ CreativeDirectionPlanner
→ política Free Tier provider-neutral
→ validación cruzada manifest/configuración
→ persistencia F3 con sidecars
→ verificación de lectura física
→ transición narracion → voz
```

El compilador recibe automáticamente tema, plataforma, duración y el perfil
provider-neutral `immersive-process-explainer-v1`. El planner deriva la
dirección visual, composición, movimiento, audio, tipos de activos y consultas
desde el storyboard y la narración aprobados.

## 4. Política Free Tier

Cuando `free_tier_default` está activo:

- `ai_image`, `ai_video` y `stock_video` se normalizan a `stock_image`;
- `motion_graphic` y `text_graphic` permanecen renderer-native;
- no se selecciona un proveedor, modelo, plantilla o cuenta concreta;
- no se adquiere ni genera ningún activo durante FAO.4;
- no se realiza red, síntesis, render, gasto ni publicación.

Las consultas stock se extraen del contenido visual aprobado mediante el
planner existente. No contienen IDs de proveedor y no se escriben a mano.

## 5. Salidas

### 5.1 `production_manifest.json`

Contrato PM1 `cips.production_manifest`, validado por Pydantic y serializado de
forma canónica. Incluye:

- identidad determinista del proyecto y la producción;
- plataforma, geometría, FPS y duración;
- narración y escenas temporizadas;
- dirección creativa;
- solicitud universal de activo por escena;
- consulta stock cuando corresponda;
- captions canónicos y diseño de audio;
- publicación editorial sin ejecutar;
- requisitos de QA y referencias SHA-256.

### 5.2 `production_acceptance_config.json`

Contrato `cips.production_acceptance.project_config` versión `1.0`, consumible
por la frontera PM9 existente. FAO.4 genera únicamente campos neutrales:

- `asset_types_by_sequence`;
- `existing_asset_ids_by_sequence`;
- `stock_queries_by_sequence`;
- rutas relativas confinadas de catálogo, activos y reporte;
- `on_screen_text_mode: captions_only`;
- política física de FPS;
- política local de conformidad acústica.

Los campos específicos de JSON2Video o Creatomate no forman parte de la
configuración generada. Cada secuencia debe corresponder exactamente a una
escena del manifest. Las consultas sólo pueden existir para activos stock y
los IDs existentes sólo para `existing_asset`.

### 5.3 `state/production_derivation.json`

Contrato `cips.fao.production_derivation` versión `1.0`. Conserva:

- fingerprint SHA-256 de todas las entradas y versiones de políticas;
- hashes y rutas de los siete entregables editoriales;
- hashes del paquete FAO.3, manifest y configuración;
- `manifest_id`, perfil, escenas, tipos y consultas;
- versiones de compiler, planner y motor FAO.4;
- `configuration_validated: true`;
- `manifest_validated: true`;
- `network_called: false`;
- `paid_provider_called: false`;
- `render_performed: false`;
- `publication_performed: false`.

Las tres salidas se persisten mediante `MetadataStore` y conservan sidecars
F3 `.meta.json`.

## 6. Idempotencia y reanudación

El `input_fingerprint` combina de forma canónica:

- SHA-256 de la solicitud operativa;
- SHA-256 del paquete editorial;
- Stage, ruta y SHA-256 de cada artefacto;
- versión del compiler;
- versión del planner;
- versión del motor de derivación;
- política Free Tier.

Si entradas, políticas y salidas son idénticas, FAO.4 reutiliza los tres
archivos byte por byte y no modifica sus sidecars. Si una entrada cambia, el
paquete FAO.3 debe volver a validarla antes de permitir una nueva derivación.

## 7. Integración con el Runtime

`PipelineEngine._validate_and_advance()` invoca FAO.4 únicamente cuando:

- el Stage completado es `narracion`; y
- existe `operational_request.json`.

Los proyectos heredados sin contrato FAO conservan su comportamiento. Si la
derivación falla, `PipelineEngine` devuelve error operativo, conserva el
proyecto en `narracion` y no declara lista la producción.

La presencia de estas salidas no autoriza adquisición de activos, síntesis de
voz, render, publicación ni consumo de créditos. Esas acciones permanecen en
fronteras posteriores y sujetas a sus gates.

## 8. Criterios de aceptación

FAO.4 se considera implementada cuando las pruebas demuestran:

1. generación automática de las tres salidas desde un proyecto FAO.3;
2. manifest PM1 válido, planificado y sin `asset_type=none`;
3. política Free Tier sin tipos AI/video stock de pago por defecto;
4. consultas derivadas y alineadas con las escenas stock;
5. configuración aceptada por `_load_project_config()` de PM9;
6. ausencia de campos específicos de proveedor en la configuración generada;
7. hashes físicos y sidecars F3 consistentes;
8. reutilización byte-idéntica ante una reejecución sin cambios;
9. bloqueo ante alteración de un artefacto editorial;
10. permanencia en `narracion` cuando FAO.4 falla;
11. cero red, proveedor pagado, render, crédito y publicación.

## 9. Exclusiones

FAO.4 no:

- ejecuta la cadena PM9;
- resuelve o descarga activos;
- sintetiza narración;
- genera subtítulos físicos;
- crea payload de render;
- estima o autoriza créditos;
- realiza render real;
- ejecuta F7/F8;
- publica contenido;
- inicia FAO.5 o PM10.
