"""
CIPS - Templates
Plantillas base para crear proyectos de contenido.
"""

from textwrap import dedent


def template_markdown(title: str, body: str = "Pendiente") -> str:
    return dedent(f"""\
    # {title}

    {body}
    """)


def tema_md(tema: str) -> str:
    return dedent(f"""\
    # Tema del Proyecto

    {tema}

    ## Objetivo inicial

    Producir contenido confiable, claro y monetizable sobre alimentación, ejercicio y salud.
    """)


def contexto_md(tema: str) -> str:
    return dedent(f"""\
    # Contexto del Proyecto

    ## Tema

    {tema}

    ## Nicho

    Alimentación, ejercicio y salud.

    ## Objetivo

    Crear contenido educativo, confiable, útil y monetizable.

    ## Público objetivo

    Personas interesadas en mejorar su salud, alimentación y condición física con información clara y basada en evidencia.

    ## Regla principal

    No exagerar beneficios. No inventar datos. Verificar afirmaciones importantes.
    """)


def proyecto_yaml(
    project_id: str,
    uuid: str,
    tema: str,
    fecha: str,
) -> dict:
    return {
        "id": project_id,
        "uuid": uuid,
        "tema": tema,
        "nicho": "alimentacion_ejercicio_salud",
        "estado": "investigacion",
        "fecha_creacion": fecha,
        "ultima_modificacion": fecha,
        "version": 1,
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


def memoria_yaml() -> dict:
    return {
        "plataforma": "pendiente",
        "duracion": "pendiente",
        "tono": "claro, cercano, confiable",
        "publico": "personas interesadas en alimentación, ejercicio y salud",
        "objetivo": "educar, generar confianza y monetizar",
        "ultimo_prompt": "",
        "ultima_respuesta": "",
        "proximo_paso": "investigacion",
    }


MARKDOWN_FILES = {
    "01_INVESTIGACION.md": "# Investigación\n\nPendiente\n",
    "02_VERIFICACION.md": "# Verificación Científica\n\nPendiente\n",
    "03_GUION.md": "# Guion\n\nPendiente\n",
    "04_STORYBOARD.md": "# Storyboard\n\nPendiente\n",
    "05_SEO.md": "# SEO\n\nPendiente\n",
    "06_PUBLICACION.md": "# Publicación\n\nPendiente\n",
    "07_FINAL.md": "# Contenido Final\n\nPendiente\n",
}