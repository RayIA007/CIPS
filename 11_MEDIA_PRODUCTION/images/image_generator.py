import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def generar_imagenes_storyboard(proyecto_dir: Path, num_escenas: int = 3) -> list[Path]:
    """
    Genera marcos verticales (1080x1920) para cada escena del storyboard.
    (Puedes sustituir este generador con Pollinations.ai, DALL-E o Stable Diffusion más adelante).
    """
    images_dir = proyecto_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    rutas_imagenes = []
    
    # Colores elegantes de fondo para el video vertical
    colores_fondo = [(20, 24, 33), (35, 43, 85), (24, 58, 55), (60, 30, 45)]

    for i in range(1, num_escenas + 1):
        img_path = images_dir / f"escena_{i:02d}.png"
        
        # Crear lienzo vertical 1080x1920 (TikTok / Short)
        img = Image.new("RGB", (1080, 1920), color=colores_fondo[i % len(colores_fondo)])
        draw = ImageDraw.Draw(img)
        
        # Dibujar un marco decorativo en el centro
        draw.rectangle([60, 60, 1020, 1860], outline=(255, 255, 255), width=6)
        
        # Guardar imagen
        img.save(img_path)
        rutas_imagenes.append(img_path)

    return rutas_imagenes