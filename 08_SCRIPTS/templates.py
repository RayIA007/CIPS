"""
CIPS - Templates
Plantillas base para crear proyectos de contenido.
"""

from textwrap import dedent


def template_markdown(
    title: str,
    body: str = "El Runtime completará este archivo automáticamente.",
) -> str:
    return dedent(f"""\
    # {title}

    {body}
    """)


def tema_md(
    tema: str,
    *,
    plataforma: str = "YouTube Shorts",
    duracion_segundos: int = 45,
    audiencia: str = "público general",
    estilo_creativo: str = "educativo, claro y dinámico",
) -> str:
    return dedent(f"""\
    # Tema del Proyecto

    {tema}

    ## Solicitud operativa

    - Plataforma: {plataforma}
    - Duración objetivo: {duracion_segundos} segundos
    - Audiencia: {audiencia}
    - Estilo creativo: {estilo_creativo}

    ## Objetivo inicial

    Producir contenido confiable, claro y adecuado para la solicitud del operador.
    """)


def contexto_md(
    tema: str,
    *,
    plataforma: str = "YouTube Shorts",
    duracion_segundos: int = 45,
    audiencia: str = "público general",
    estilo_creativo: str = "educativo, claro y dinámico",
) -> str:
    return dedent(f"""\
    # Contexto del Proyecto

    ## Tema

    {tema}

    ## Plataforma

    {plataforma}

    ## Duración objetivo

    {duracion_segundos} segundos.

    ## Público objetivo

    {audiencia}

    ## Estilo creativo

    {estilo_creativo}

    ## Objetivo

    Crear contenido útil, verificable y apropiado para la plataforma y la audiencia indicadas.

    ## Regla principal

    No exagerar beneficios. No inventar datos. Verificar afirmaciones importantes.
    """)


def proyecto_yaml(
    project_id: str,
    uuid: str,
    tema: str,
    fecha: str,
    *,
    plataforma: str = "YouTube Shorts",
    duracion_segundos: int = 45,
    audiencia: str = "público general",
    estilo_creativo: str = "educativo, claro y dinámico",
) -> dict:
    return {
        "id": project_id,
        "uuid": uuid,
        "tema": tema,
        "estado": "investigacion",
        "stage_actual": "investigacion",
        "ultimo_stage_validado": "",
        "fecha_creacion": fecha,
        "ultima_modificacion": fecha,
        "version": 1,
        "solicitud_operativa": {
            "schema_name": "cips.fao.operational_request",
            "schema_version": "1.0",
            "topic": tema,
            "platform": plataforma,
            "duration_seconds": duracion_segundos,
            "audience": audiencia,
            "creative_style": estilo_creativo,
            "publication_performed": False,
        },
        "pipeline": {
            "00_tema": "completado",
            "01_investigacion": "pendiente",
            "02_verificacion": "pendiente",
            "03_guion": "pendiente",
            "04_storyboard": "pendiente",
            "05_seo": "pendiente",
            "06_publicacion": "pendiente",
            "07_final": "pendiente",
        },
    }


def memoria_yaml(
    *,
    plataforma: str = "YouTube Shorts",
    duracion_segundos: int = 45,
    audiencia: str = "público general",
    estilo_creativo: str = "educativo, claro y dinámico",
) -> dict:
    return {
        "plataforma": plataforma,
        "duracion": duracion_segundos,
        "tono": estilo_creativo,
        "publico": audiencia,
        "objetivo": "producir contenido confiable y apropiado para la solicitud",
        "ultimo_prompt": "",
        "ultima_respuesta": "",
        "proximo_paso": "investigacion",
    }


MARKDOWN_FILES = {
    "01_INVESTIGACION.md": "# Investigación\n\nEl Runtime sincronizará aquí el entregable validado.\n",
    "02_VERIFICACION.md": "# Verificación Científica\n\nEl Runtime sincronizará aquí el entregable validado.\n",
    "03_GUION.md": "# Guion\n\nEl Runtime sincronizará aquí el entregable validado.\n",
    "04_STORYBOARD.md": "# Storyboard\n\nEl Runtime sincronizará aquí el entregable validado.\n",
    "05_SEO.md": "# SEO\n\nEl Runtime sincronizará aquí el entregable validado.\n",
    "06_PUBLICACION.md": "# Publicación\n\nEl Runtime sincronizará aquí el entregable validado.\n",
    "07_FINAL.md": "# Contenido Final\n\nLa finalización posterior generará este artefacto; no se ha publicado contenido.\n",
}
