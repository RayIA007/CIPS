import os

# Configuración del archivo de salida
OUTPUT_FILE = "PROYECTO_CONSEJO_EXPERTOS.txt"

# Carpetas y extensiones a ignorar para mantener el archivo limpio y gratuito
IGNORE_DIRS = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', '.idea', '.vscode'}
IGNORE_EXTS = {'.pyc', '.exe', '.png', '.jpg', '.jpeg', '.mp4', '.mp3', '.zip', '.tar', '.gz'}

# Encabezado con el contexto y la misión para la IA
HEADER_CONTEXT = """================================================================================
PROYECTO: CONSEJO DE EXPERTOS IA MULTIDISCIPLINAR (MVP AUTOMATIZADO)
OBJETIVO: Finalizar la orquestación de agentes y publicar el primer contenido a costo $0.
================================================================================

INSTRUCCIONES PARA LA IA:
Actúa como Arquitecto Senior de IA y Programador Full Stack. 
A continuación se presenta el código completo y la estructura del proyecto.
1. Analiza la arquitectura y los prompts de los agentes.
2. Detecta errores, partes faltantes o cuellos de botella en la orquestación.
3. Devuelve el código corregido o completado listo para ejecutar en local sin costo.

================================================================================
ESTRUCTURA DE ARCHIVOS Y CÓDIGO FUENTE
================================================================================
"""

def generate_unified_txt():
    root_dir = os.getcwd()
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        outfile.write(HEADER_CONTEXT + "\n\n")
        
        for current_root, dirs, files in os.walk(root_dir):
            # Filtrar carpetas ignoradas
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in IGNORE_EXTS or file == OUTPUT_FILE or file == "consolidar_proyecto.py":
                    continue
                
                file_path = os.path.join(current_root, file)
                rel_path = os.path.relpath(file_path, root_dir)
                
                outfile.write(f"--- INICIO ARCHIVO: {rel_path} ---\n")
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"[Error al leer el archivo: {e}]\n")
                outfile.write(f"\n--- FIN ARCHIVO: {rel_path} ---\n\n")

    print(f"✅ ¡Proyecto unificado con éxito en '{OUTPUT_FILE}'!")

if __name__ == "__main__":
    generate_unified_txt()