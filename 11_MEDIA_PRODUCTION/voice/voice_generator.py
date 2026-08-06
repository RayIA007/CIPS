import asyncio
import re
from pathlib import Path
import edge_tts


def limpiar_texto_guion(texto_markdown: str) -> str:
    """Elimina encabezados, acotaciones entre corchetes y formato Markdown para la locución."""
    # Eliminar acotaciones tipo [Musica de fondo], (Pausa), etc.
    texto_limpio = re.sub(r"\[.*?\]|\(.*?\)", "", texto_markdown)
    # Eliminar caracteres especiales de Markdown (#, *, _, etc.)
    texto_limpio = re.sub(r"[#*_`~]", "", texto_limpio)
    # Quitar saltos de línea excesivos
    lineas = [linea.strip() for linea in texto_limpio.splitlines() if linea.strip()]
    return " ".join(lineas)


async def generar_audio_async(texto: str, output_path: Path, voice: str = "es-MX-JorgeNeural"):
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(str(output_path))


def generar_voz_desde_guion(proyecto_dir: Path) -> Path:
    guion_path = proyecto_dir / "script" / "03_GUION.md"
    audio_path = proyecto_dir / "voice" / "audio.mp3"

    # Si existe el guion real lo usa; de lo contrario, aplica un texto por defecto de prueba
    if guion_path.exists():
        with open(guion_path, "r", encoding="utf-8") as f:
            contenido_guion = f.read()
        texto_para_locucion = limpiar_texto_guion(contenido_guion)
    else:
        print("    [Warning] No se encontró 03_GUION.md, generando locución de prueba.")
        texto_para_locucion = "Bienvenido a CIPS. Este es un video de prueba generado automáticamente por el sistema."

    # Guardar narración limpia en texto plano
    narracion_path = proyecto_dir / "narration" / "narration.txt"
    narracion_path.parent.mkdir(parents=True, exist_ok=True)
    with open(narracion_path, "w", encoding="utf-8") as f:
        f.write(texto_para_locucion)

    # Generar audio MP3
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(generar_audio_async(texto_para_locucion, audio_path))

    return audio_path