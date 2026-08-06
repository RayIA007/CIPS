from pathlib import Path
from moviepy import AudioFileClip, ImageClip, concatenate_videoclips


def ensamblar_video_vertical(proyecto_dir: Path) -> Path:
    audio_path = proyecto_dir / "voice" / "audio.mp3"
    images_dir = proyecto_dir / "images"
    output_video_path = proyecto_dir / "final" / "short.mp4"

    if not audio_path.exists():
        raise FileNotFoundError(f"Archivo de voz no encontrado: {audio_path}")

    # Cargar audio de locución
    audio_clip = AudioFileClip(str(audio_path))
    duracion_total = audio_clip.duration

    # Obtener lista de imágenes
    imagenes = sorted(list(images_dir.glob("*.png")))
    if not imagenes:
        raise FileNotFoundError("No se encontraron imágenes en la carpeta images/")

    duracion_por_imagen = duracion_total / len(imagenes)

    # Crear clips de imagen ajustados al tiempo del audio
    clips = []
    for img_path in imagenes:
        clip = ImageClip(str(img_path)).with_duration(duracion_por_imagen)
        clips.append(clip)

    # Concatenar secuencia de imágenes y asignar audio
    video_final = concatenate_videoclips(clips, method="compose")
    video_final = video_final.with_audio(audio_clip)

    # Asegurar que el directorio de salida existe
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    # Renderizar el video vertical en formato MP4 (1080x1920)
    video_final.write_videofile(
        str(output_video_path),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None # Desactiva logs ruidosos en consola
    )

    audio_clip.close()
    video_final.close()

    return output_video_path