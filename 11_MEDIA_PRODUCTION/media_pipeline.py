import sys
from pathlib import Path

# Asegurar que el directorio 11_MEDIA_PRODUCTION esté en el path de Python
MEDIA_DIR = Path(__file__).resolve().parent
if str(MEDIA_DIR) not in sys.path:
    sys.path.append(str(MEDIA_DIR))

# Importaciones directas de los módulos
from voice.voice_generator import generar_voz_desde_guion
from images.image_generator import generar_imagenes_storyboard
from assembly.video_assembler import ensamblar_video_vertical


def ejecutar_media_production(proyecto_dir: Path) -> bool:
    """
    Ejecuta en secuencia la producción audiovisual completa:
    1. Locución (Voz/TTS)
    2. Generación de imágenes
    3. Ensamblado del video vertical (short.mp4)
    """
    try:
        print("    [Media] Generando voz de locución...")
        generar_voz_desde_guion(proyecto_dir)

        print("    [Media] Generando activos visuales...")
        generar_imagenes_storyboard(proyecto_dir)

        print("    [Media] Renderizando video vertical (short.mp4)...")
        ensamblar_video_vertical(proyecto_dir)

        return True
    except Exception as e:
        print(f"    [Media Error] Fallo en la producción multimedia: {e}")
        return False