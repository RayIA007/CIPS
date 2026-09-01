---
document:
  id: FAO-OPS-002
  title: Integración de Entrada Oficial y Proyecto Fresco
  version: 1.0.0
  status: IMPLEMENTED
  classification: Production System Contract
  owner: ConsejoIA_V5 Architecture
  repository: ConsejoIA_V5
---

# 1. Propósito

Esta especificación define la implementación de `FAO.2 — Integración de la
entrada oficial y proyecto fresco`. Amplía la opción `1 — Nuevo Proyecto` de
la interfaz existente iniciada por `CIPS/run.py`; no crea otro CLI ni conecta
todavía la automatización editorial de FAO.3 o la cadena PM9 de FAO.5.

# 2. Alcance

FAO.2 incorpora exclusivamente:

- captura de tema, plataforma, duración, audiencia y estilo creativo;
- creación de un workspace fresco compatible con la estructura heredada y la
  estructura moderna de stages;
- persistencia provider-neutral de la solicitud operativa;
- checkpoint inicial mediante `ProductionStateManager`;
- selección de un proyecto reanudable desde `2 — Continuar Proyecto` sin pedir
  rutas internas;
- sincronización del `current_stage` del checkpoint después de cada transición;
- conservación de Free Tier y `publication_performed: false`.

FAO.2 no genera investigación, guion, storyboard ni configuración de
producción. Tampoco adquiere activos, invoca un render, consume créditos,
ejecuta PM9, toma una decisión F7/F8 ni publica.

# 3. Entrada oficial

```text
CIPS/run.py
→ build_menu()
→ opción 1 — Nuevo Proyecto
→ MenuController.new_project()
→ ProjectManager.create_project(...)
```

Los cinco campos del contrato FAO.1 se solicitan desde el menú existente:

| Campo contractual | Entrada visible | Valor predeterminado |
|---|---|---|
| `topic` | ¿Qué vamos a publicar hoy? | ninguno |
| `platform` | Plataforma | `YouTube Shorts` |
| `duration_seconds` | Duración objetivo | `45` |
| `audience` | Audiencia | `público general` |
| `creative_style` | Estilo creativo | `educativo, claro y dinámico` |

La duración admite enteros entre 1 y 3600 segundos. El operador no introduce
rutas, nombres de archivos, JSON, Markdown, proveedores ni opciones internas.

# 4. Workspace fresco

Cada proyecto conserva los directorios heredados y añade las fronteras físicas
usadas por el runtime moderno:

```text
PROYECTO_NNNN/
├── 01_FUENTES/ ... 06_EXPORTACIONES/
├── research/ verification/ script/ storyboard/
├── narration/ seo/ publication/
├── assets/ voice/ images/ subtitles/ video/ final/
├── state/production_state.json
├── operational_request.json
├── production.json
├── proyecto.yaml
├── memoria.yaml
├── 00_TEMA.md
└── CONTEXTO.md
```

Las plantillas ya no imponen el nicho histórico de salud. El tema y las cuatro
preferencias se propagan a `operational_request.json`, `proyecto.yaml`,
`memoria.yaml`, `00_TEMA.md` y `CONTEXTO.md`.

# 5. Solicitud operativa

`operational_request.json` utiliza:

```json
{
  "schema_name": "cips.fao.operational_request",
  "schema_version": "1.0",
  "project_id": "PROYECTO_NNNN",
  "project_uuid": "uuid",
  "topic": "tema del operador",
  "platform": "plataforma",
  "duration_seconds": 45,
  "audience": "audiencia",
  "creative_style": "estilo",
  "created_at": "YYYY-MM-DD HH:MM:SS",
  "free_tier_default": true,
  "publication_performed": false
}
```

La escritura de los archivos JSON se realiza mediante reemplazo atómico. La
API histórica `ProjectManager.create_project(tema)` sigue siendo válida y usa
los valores predeterminados del menú.

# 6. Checkpoint y reanudación

La creación inicializa `state/production_state.json` mediante el componente
existente `ProductionStateManager`:

| Propiedad | Valor inicial |
|---|---|
| schema FAO | `cips.fao.project_checkpoint` 1.0 |
| lifecycle | `project_created` |
| current stage | `investigacion` |
| snapshot | `project_created` |
| publicación | `false` |

Antes de ejecutar el runtime se persiste `runtime_started`. Una pausa, fallo o
solicitud de reanudación añade un snapshot auditable sin borrar el historial.
Cuando `PipelineEngine` avanza un stage, el `current_stage` de
`ProductionStateManager` se actualiza al mismo `next_stage` persistido en
`proyecto.yaml`.

La opción `2 — Continuar Proyecto`:

1. enumera primero los workspaces que contienen solicitud y checkpoint FAO;
2. muestra ID, tema y stage actual;
3. recibe sólo un número de la lista, con el último como predeterminado;
4. ejecuta `PipelineEngine.execute(project_path=...)` sobre la selección;
5. persiste `resume_requested` y el resultado del paso;
6. mantiene `publication_performed: false`.

Si aún no existe un proyecto FAO, la opción conserva compatibilidad con los
proyectos heredados que contienen `proyecto.yaml`.

# 7. Invariantes

1. `CIPS/run.py` permanece como entrada principal.
2. Las opciones `1` y `2` del menú existente siguen siendo las fronteras del
   operador.
3. La ruta heredada a `ejecutar_media_production` se conserva; su importación
   es diferida hasta la ejecución para que inspección y selección no carguen
   backends multimedia.
4. `ProductionManifest` permanece provider-neutral.
5. Free Tier continúa como política predeterminada.
6. Ningún crédito se consume y ningún render se ejecuta en FAO.2.
7. `publication_performed` permanece en `false`.
8. El proyecto PM9 del cielo no se modifica ni se selecciona como último
   proyecto fresco por su nombre especial.
9. FAO.3 y PM10 permanecen bloqueadas.

# 8. Validación

La prueba `08_SCRIPTS/tests/test_fao_project_entry_resume.py` verifica:

- persistencia exacta de los cinco campos;
- estructura fresca heredada y moderna;
- checkpoint inicial y publicación desactivada;
- compatibilidad de `create_project(tema)`;
- rechazo de duración inválida antes de crear un workspace;
- prioridad del último proyecto numérico sobre proyectos especiales cerrados;
- selección y reanudación por número, sin introducir una ruta;
- pausa recuperable desde la entrada oficial;
- ausencia de ejecución multimedia durante una pausa editorial.

La regresión incluye también el baseline FAO.1, que debe continuar demostrando
que la conexión con PM9 sigue ausente hasta FAO.5.
