"""
=========================================================
CIPS
Menú Principal
=========================================================
"""

from rich.table import Table


def build_menu():

    table = Table(
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Opción", justify="center", width=8)
    table.add_column("Descripción")

    # -----------------------------
    # PROYECTOS
    # -----------------------------

    table.add_section()

    table.add_row(
        "[bold yellow]PROYECTOS[/bold yellow]",
        ""
    )

    table.add_row("1", "Nuevo Proyecto")
    table.add_row("2", "Continuar Proyecto")

    # -----------------------------
    # KNOWLEDGE
    # -----------------------------

    table.add_section()

    table.add_row(
        "[bold yellow]KNOWLEDGE[/bold yellow]",
        ""
    )

    table.add_row(
        "5",
        "Crear Knowledge Module v2"
    )

    # -----------------------------
    # SISTEMA
    # -----------------------------

    table.add_section()

    table.add_row(
        "[bold yellow]SISTEMA[/bold yellow]",
        ""
    )

    table.add_row("3", "Configuración")
    table.add_row("4", "Estado del Sistema")
    table.add_row("7", "Pruebas del Runtime")

    table.add_section()

    table.add_row("0", "Salir")

    return table