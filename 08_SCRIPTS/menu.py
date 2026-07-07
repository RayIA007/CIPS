"""
=========================================================
CIPS
Menú Principal
=========================================================
"""

from rich.table import Table


def build_menu():

    tabla = Table(show_header=True)

    tabla.add_column("Opción", justify="center")

    tabla.add_column("Descripción")

    tabla.add_row("1", "Nuevo Proyecto")

    tabla.add_row("2", "Continuar Proyecto")

    tabla.add_row("3", "Configuración")

    tabla.add_row("4", "Estado del Sistema")

    tabla.add_row("0", "Salir")

    return tabla