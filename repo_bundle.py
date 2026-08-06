#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
repo_bundle.py
Empaqueta un proyecto completo en un solo archivo de texto para analisis con LLM.
Uso desde PowerShell:
    python repo_bundle.py "C:\ConsejoIA_V5" --output "C:\temp\bundle_consejo.txt"
    python repo_bundle.py "C:\Universal Architecture Audit Framework (UAAF)" --output "C:\temp\bundle_uaaf.txt"
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------------------

EXTENSIONES_RELEVANTES = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".json", ".toml",
    ".cfg", ".ini", ".rst", ".html", ".css", ".js", ".ts",
    ".sql", ".sh", ".bat", ".ps1", ".dockerfile", ".gitignore",
    ".lock", ".pip", ".requirements", ".env.example",
}

EXCLUSIONES_POR_DEFECTO = {
    "__pycache__", ".git", ".venv", "venv", "env", "node_modules",
    ".pytest_cache", ".mypy_cache", ".tox", "dist", "build",
    ".idea", ".vscode", "*.egg-info", ".coverage", "htmlcov",
    ".DS_Store", "Thumbs.db", ".gitattributes",
}

LIMITE_TAMANO_ARCHIVO_MB = 2

# ---------------------------------------------------------------------------
# FUNCIONES
# ---------------------------------------------------------------------------

def es_excluido(ruta: Path, exclusiones: set) -> bool:
    for parte in ruta.parts:
        if parte in exclusiones:
            return True
        for exc in exclusiones:
            if exc.startswith("*") and parte.endswith(exc.lstrip("*")):
                return True
    return False


def es_relevante(ruta: Path) -> bool:
    if ruta.suffix.lower() in EXTENSIONES_RELEVANTES:
        return True
    if ruta.name.lower() in {".gitignore", "dockerfile", "makefile", "license"}:
        return True
    return False


def leer_archivo_seguro(ruta: Path):
    try:
        tamano = ruta.stat().st_size
        if tamano > LIMITE_TAMANO_ARCHIVO_MB * 1024 * 1024:
            return f"[ARCHIVO OMITIDO: {tamano / (1024*1024):.1f} MB - excede limite de {LIMITE_TAMANO_ARCHIVO_MB} MB]\n"
        try:
            return ruta.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ruta.read_text(encoding="latin-1")
    except Exception as e:
        return f"[ERROR AL LEER: {e}]\n"


def generar_bundle(ruta_proyecto: Path, ruta_salida: Path, exclusiones: set):
    archivos_incluidos = 0
    archivos_omitidos = 0
    lineas_totales = 0

    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f" BUNDLE DE PROYECTO: {ruta_proyecto.name}\n")
        f.write(f" RUTA ORIGINAL: {ruta_proyecto.resolve()}\n")
        f.write(f" FECHA DE GENERACION: {datetime.now().isoformat()}\n")
        f.write(f" GENERADO POR: repo_bundle.py\n")
        f.write("=" * 80 + "\n\n")

        for raiz, dirs, archivos in os.walk(ruta_proyecto):
            ruta_raiz = Path(raiz)
            dirs[:] = [d for d in dirs if not es_excluido(ruta_raiz / d, exclusiones)]

            for nombre_archivo in sorted(archivos):
                ruta_archivo = ruta_raiz / nombre_archivo
                if es_excluido(ruta_archivo, exclusiones):
                    continue
                if not es_relevante(ruta_archivo):
                    archivos_omitidos += 1
                    continue

                ruta_relativa = ruta_archivo.relative_to(ruta_proyecto)
                contenido = leer_archivo_seguro(ruta_archivo)
                if contenido is None:
                    continue

                f.write("-" * 80 + "\n")
                f.write(f"ARCHIVO: {ruta_relativa}\n")
                f.write(f"RUTA COMPLETA: {ruta_archivo}\n")
                f.write("-" * 80 + "\n")
                f.write(contenido)
                if not contenido.endswith("\n"):
                    f.write("\n")
                f.write("\n")

                archivos_incluidos += 1
                lineas_totales += contenido.count("\n")

        f.write("=" * 80 + "\n")
        f.write(" RESUMEN\n")
        f.write("=" * 80 + "\n")
        f.write(f" Archivos incluidos: {archivos_incluidos}\n")
        f.write(f" Archivos omitidos (no relevantes): {archivos_omitidos}\n")
        f.write(f" Lineas totales: {lineas_totales}\n")
        f.write("=" * 80 + "\n")

    return archivos_incluidos, archivos_omitidos, lineas_totales


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Empaqueta un proyecto en un solo archivo de texto para LLMs."
    )
    parser.add_argument("proyecto", help="Ruta de la carpeta raiz del proyecto")
    parser.add_argument(
        "--output", "-o",
        help="Ruta del archivo de salida (default: bundle_<nombre>.txt en el directorio actual)"
    )
    parser.add_argument(
        "--excluir", "-e",
        nargs="+",
        default=[],
        help="Carpetas o patrones adicionales a excluir"
    )

    args = parser.parse_args()

    ruta_proyecto = Path(args.proyecto).resolve()
    if not ruta_proyecto.exists():
        print(f"[ERROR] La ruta no existe: {ruta_proyecto}")
        sys.exit(1)
    if not ruta_proyecto.is_dir():
        print(f"[ERROR] No es un directorio: {ruta_proyecto}")
        sys.exit(1)

    if args.output:
        ruta_salida = Path(args.output).resolve()
    else:
        ruta_salida = Path.cwd() / f"bundle_{ruta_proyecto.name}.txt"

    # Crear directorios intermedios si no existen
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    exclusiones = EXCLUSIONES_POR_DEFECTO | set(args.excluir)

    print(f"Empaquetando: {ruta_proyecto}")
    print(f"Salida: {ruta_salida}")
    print(f"Exclusiones: {', '.join(sorted(exclusiones))}")
    print("Procesando...\n")

    incluidos, omitidos, lineas = generar_bundle(ruta_proyecto, ruta_salida, exclusiones)
    tamano_mb = ruta_salida.stat().st_size / (1024 * 1024)

    print(f"Listo.")
    print(f"   Archivos incluidos: {incluidos}")
    print(f"   Archivos omitidos:  {omitidos}")
    print(f"   Lineas totales:     {lineas}")
    print(f"   Tamano del bundle:  {tamano_mb:.2f} MB")
    print(f"\nArchivo generado: {ruta_salida}")


if __name__ == "__main__":
    main()
