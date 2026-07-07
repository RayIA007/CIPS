"""
=====================================================
CIPS
Project Manager
=====================================================
"""

from pathlib import Path
from datetime import datetime
import uuid
import yaml


PROYECTOS_DIR = Path("04_PROYECTOS")


class ProjectManager:

    def __init__(self):

        PROYECTOS_DIR.mkdir(exist_ok=True)

    # ----------------------------------------

    def obtener_siguiente_id(self):

        proyectos = sorted(PROYECTOS_DIR.glob("PROYECTO_*"))

        if not proyectos:

            return 1

        ultimo = proyectos[-1].name

        numero = int(ultimo.split("_")[1])

        return numero + 1

    # ----------------------------------------

    def crear_proyecto(self, tema):

        numero = self.obtener_siguiente_id()

        nombre = f"PROYECTO_{numero:04d}"

        carpeta = PROYECTOS_DIR / nombre

        carpeta.mkdir()

        (carpeta / "prompts").mkdir()

        (carpeta / "recursos").mkdir()

        (carpeta / "outputs").mkdir()

        archivos = [

            "tema.md",

            "investigacion.md",

            "verificacion.md",

            "guion.md",

            "storyboard.md",

            "seo.md",

            "publicacion.md"

        ]

        for archivo in archivos:

            (carpeta / archivo).touch()

        with open(carpeta / "tema.md", "w", encoding="utf-8") as f:

            f.write(f"# Tema\n\n{tema}\n")

        metadata = {

            "id": nombre,

            "uuid": str(uuid.uuid4()),

            "tema": tema,

            "estado": "investigacion",

            "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            "version": 1

        }

        with open(carpeta / "proyecto.yaml", "w", encoding="utf-8") as f:

            yaml.dump(metadata, f, allow_unicode=True, sort_keys=False)

        return nombre