#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
split_bundle.py
Divide un archivo bundle en N partes respetando los limites de archivo internos.
Uso desde PowerShell:
    python split_bundle.py "C:\temp\bundle_cips.txt" --parts 5
    python split_bundle.py "C:\temp\bundle_cips.txt" --max-mb 1.0
"""

import sys
import argparse
from pathlib import Path


def encontrar_limites(texto: str, separador: str) -> list[int]:
    """Encuentra todas las posiciones del separador en el texto."""
    limites = []
    inicio = 0
    while True:
        pos = texto.find(separador, inicio)
        if pos == -1:
            break
        limites.append(pos)
        inicio = pos + len(separador)
    return limites


def dividir_por_partes(ruta_entrada: Path, num_partes: int):
    texto = ruta_entrada.read_text(encoding="utf-8")
    separador = "-" * 80 + "\nARCHIVO:"
    limites = encontrar_limites(texto, separador)

    if not limites:
        print("[ERROR] No se encontraron separadores de archivo en el bundle.")
        sys.exit(1)

    total_archivos = len(limites)
    archivos_por_parte = total_archivos // num_partes
    resto = total_archivos % num_partes

    print(f"Archivos totales encontrados: {total_archivos}")
    print(f"Dividiendo en {num_partes} parte(s)...\n")

    idx = 0
    parte_actual = 1
    archivos_en_parte = archivos_por_parte + (1 if resto > 0 else 0)
    resto -= 1 if resto > 0 else 0

    inicio = 0
    archivos_contados = 0

    for i, limite in enumerate(limites):
        archivos_contados += 1
        if archivos_contados >= archivos_en_parte and parte_actual < num_partes:
            fin = limite
            contenido = texto[inicio:fin]
            ruta_salida = ruta_entrada.parent / f"{ruta_entrada.stem}_part{parte_actual}{ruta_entrada.suffix}"
            ruta_salida.write_text(contenido, encoding="utf-8")
            tamano_mb = len(contenido.encode("utf-8")) / (1024 * 1024)
            print(f"  Parte {parte_actual}: {ruta_salida.name} ({tamano_mb:.2f} MB, {archivos_contados} archivos)")

            inicio = fin
            parte_actual += 1
            archivos_contados = 0
            archivos_en_parte = archivos_por_parte + (1 if resto > 0 else 0)
            resto -= 1 if resto > 0 else 0

    # Ultima parte: todo lo que queda
    contenido = texto[inicio:]
    ruta_salida = ruta_entrada.parent / f"{ruta_entrada.stem}_part{parte_actual}{ruta_entrada.suffix}"
    ruta_salida.write_text(contenido, encoding="utf-8")
    tamano_mb = len(contenido.encode("utf-8")) / (1024 * 1024)
    print(f"  Parte {parte_actual}: {ruta_salida.name} ({tamano_mb:.2f} MB, {archivos_contados} archivos)")

    print(f"\nListo. Archivos generados en: {ruta_entrada.parent}")


def dividir_por_tamano(ruta_entrada: Path, max_mb: float):
    texto = ruta_entrada.read_text(encoding="utf-8")
    separador = "-" * 80 + "\nARCHIVO:"
    limites = encontrar_limites(texto, separador)

    if not limites:
        print("[ERROR] No se encontraron separadores de archivo en el bundle.")
        sys.exit(1)

    max_bytes = int(max_mb * 1024 * 1024)
    parte_actual = 1
    inicio = 0
    archivos_contados = 0
    archivos_totales = 0

    print(f"Dividiendo por tamano maximo de {max_mb:.1f} MB...\n")

    for i, limite in enumerate(limites):
        candidato = texto[inicio:limite]
        bytes_candidato = len(candidato.encode("utf-8"))

        if bytes_candidato > max_bytes and archivos_contados > 0:
            # Cerrar parte anterior
            fin = limites[i - 1] if i > 0 else inicio
            contenido = texto[inicio:fin]
            ruta_salida = ruta_entrada.parent / f"{ruta_entrada.stem}_part{parte_actual}{ruta_entrada.suffix}"
            ruta_salida.write_text(contenido, encoding="utf-8")
            tamano_mb = len(contenido.encode("utf-8")) / (1024 * 1024)
            print(f"  Parte {parte_actual}: {ruta_salida.name} ({tamano_mb:.2f} MB, {archivos_contados} archivos)")

            inicio = fin
            parte_actual += 1
            archivos_contados = 0

        archivos_contados += 1
        archivos_totales += 1

    # Ultima parte
    contenido = texto[inicio:]
    ruta_salida = ruta_entrada.parent / f"{ruta_entrada.stem}_part{parte_actual}{ruta_entrada.suffix}"
    ruta_salida.write_text(contenido, encoding="utf-8")
    tamano_mb = len(contenido.encode("utf-8")) / (1024 * 1024)
    print(f"  Parte {parte_actual}: {ruta_salida.name} ({tamano_mb:.2f} MB, {archivos_contados} archivos)")

    print(f"\nListo. Total: {archivos_totales} archivos en {parte_actual} parte(s).")
    print(f"Generados en: {ruta_entrada.parent}")


def main():
    parser = argparse.ArgumentParser(
        description="Divide un bundle en partes mas pequenas."
    )
    parser.add_argument("entrada", help="Ruta del archivo bundle a dividir")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument(
        "--parts", "-p", type=int,
        help="Numero de partes a generar"
    )
    grupo.add_argument(
        "--max-mb", "-m", type=float,
        help="Tamano maximo por parte en MB"
    )

    args = parser.parse_args()

    ruta_entrada = Path(args.entrada).resolve()
    if not ruta_entrada.exists():
        print(f"[ERROR] Archivo no encontrado: {ruta_entrada}")
        sys.exit(1)

    tamano_total_mb = ruta_entrada.stat().st_size / (1024 * 1024)
    print(f"Archivo: {ruta_entrada.name}")
    print(f"Tamano total: {tamano_total_mb:.2f} MB\n")

    if args.parts:
        dividir_por_partes(ruta_entrada, args.parts)
    else:
        dividir_por_tamano(ruta_entrada, args.max_mb)


if __name__ == "__main__":
    main()
