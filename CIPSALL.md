┌──────────────────────────────────────────────────────────────┐
│                 CIPS — SISTEMA EDITORIAL                     │
└──────────────────────────────────────────────────────────────┘

Usuario
  │
  │  python C:\ConsejoIA_V5\CIPS\run.py
  ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. CAPA DE ENTRADA                                           │
│                                                              │
│ CIPS\run.py                                                  │
│                                                              │
│ • Inicia CIPS                                                │
│ • Carga configuración                                        │
│ • Presenta el menú                                           │
│ • Recibe la opción del usuario                               │
│ • Entrega el control a MenuController                        │
└──────────────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. CAPA DE INTERFAZ Y CONTROL                                │
│                                                              │
│ 08_SCRIPTS\menu.py                                           │
│ 08_SCRIPTS\menu_controller.py                                │
│                                                              │
│ • Construye las opciones del menú                            │
│ • Interpreta la orden seleccionada                           │
│ • Decide qué operación o pipeline iniciar                    │
└──────────────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. CAPA DE APLICACIÓN Y ORQUESTACIÓN                         │
│                                                              │
│ Agent Runtime / CIPS Core                                    │
│ core_orchestrator.py                                         │
│ pipeline_runner.py                                           │
│ pipeline_engine.py                                           │
│ content_pipeline.py                                          │
│                                                              │
│ • Crea la ejecución                                          │
│ • Transporta el contexto                                     │
│ • Coordina etapas                                            │
│ • Administra errores y reintentos                            │
│ • Registra sesiones y eventos                                │
│ • Devuelve resultados normalizados                           │
└──────────────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. DIRECCIÓN EDITORIAL                                       │
│                                                              │
│ master_producer.py                                           │
│ master_producer_models.py                                    │
│ master_producer_prompt_builder.py                            │
│                                                              │
│ • Interpreta el encargo editorial                            │
│ • Define objetivos de producción                             │
│ • Selecciona etapas y especialistas                          │
│ • Construye el plan maestro                                  │
│ • Supervisa el resultado general                             │
└──────────────────────────────────────────────────────────────┘
  │
  ├──────────────────────────┐
  ▼                          ▼
┌───────────────────────┐  ┌───────────────────────────────────┐
│ 5. ESTRATEGIA         │  │ 6. INVESTIGACIÓN                 │
│                       │  │                                   │
│ strategy_director\    │  │ research_stage.py                │
│ engine.py             │  │ research_director_models.py      │
│ models.py             │  │ research_director_prompt_builder │
│                       │  │ research_prompt\                  │
│ • Audiencia           │  │                                   │
│ • Plataforma          │  │ • Plan de investigación          │
│ • Objetivo            │  │ • Fuentes y evidencias           │
│ • Posicionamiento     │  │ • Análisis del tema              │
│ • Formato             │  │ • Hallazgos relevantes           │
└───────────────────────┘  └───────────────────────────────────┘
  │                          │
  └──────────────┬───────────┘
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. CONSEJO DE EXPERTOS Y CONOCIMIENTO                        │
│                                                              │
│ expert_council_stage.py                                      │
│ knowledge_engine.py                                          │
│ knowledge_resolver.py                                        │
│ knowledge_injector.py                                        │
│ 09_KNOWLEDGE\                                                │
│                                                              │
│ • Consulta políticas editoriales                             │
│ • Aplica conocimiento especializado                          │
│ • Integra criterios científicos y estratégicos               │
│ • Enriquece el contexto de producción                        │
└──────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 8. PRODUCCIÓN DE CONTENIDO                                   │
│                                                              │
│ content_director\                                            │
│ script_stage.py                                              │
│ prompt_builder.py                                            │
│ prompt_engine.py                                             │
│ prompt_renderer.py                                           │
│                                                              │
│ • Planeación del contenido                                   │
│ • Desarrollo del concepto                                    │
│ • Escritura del guion                                        │
│ • Storyboard                                                 │
│ • SEO                                                        │
│ • Publicación                                                │
│ • Prompts para imágenes, video y narración                   │
└──────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 9. EJECUCIÓN CON MODELOS DE IA                               │
│                                                              │
│ llm_manager.py                                               │
│ llm_adapter.py                                               │
│ provider_registry.py                                         │
│ openai_provider.py                                           │
│ gemini_llm_provider.py                                       │
│ ollama_provider.py                                           │
│ manual_llm_provider.py                                       │
│ mock_provider.py                                             │
│                                                              │
│ • Selecciona proveedor                                       │
│ • Envía prompts                                              │
│ • Gestiona respuestas                                        │
│ • Controla reintentos                                        │
│ • Permite pruebas sin consumir servicios reales              │
└──────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 10. VALIDACIÓN Y FINALIZACIÓN                                │
│                                                              │
│ validator_engine.py                                          │
│ finalization_engine.py                                       │
│ final_project_builder.py                                     │
│ export_engine.py                                             │
│                                                              │
│ • Comprueba integridad                                       │
│ • Valida entregables                                         │
│ • Consolida el proyecto                                      │
│ • Prepara versiones finales                                  │
└──────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 11. PERSISTENCIA EDITORIAL                                   │
│                                                              │
│ 04_PROYECTOS\<PROYECTO>\                                     │
│ 05_OUTPUTS\<PLATAFORMA>\<EJECUCIÓN>\                         │
│                                                              │
│ • Investigación                                              │
│ • Verificación                                               │
│ • Guion                                                      │
│ • Storyboard                                                 │
│ • SEO                                                        │
│ • Publicación                                                │
│ • Recursos multimedia                                        │
│ • Resultado final                                            │
└──────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 12. OBSERVABILIDAD Y CONTROL                                 │
│                                                              │
│ telemetry_engine.py                                          │
│ runtime_health_monitor.py                                    │
│ metrics_engine.py                                            │
│ cost_analyzer.py                                             │
│ dashboard_generator.py                                       │
│ dashboard_exporter.py                                        │
│ 07_LOGS\                                                     │
│                                                              │
│ • Logs                                                       │
│ • Tiempos de ejecución                                       │
│ • Uso y costos                                               │
│ • Errores                                                    │
│ • Estado del pipeline                                        │
│ • Dashboard ejecutivo                                        │
└──────────────────────────────────────────────────────────────┘