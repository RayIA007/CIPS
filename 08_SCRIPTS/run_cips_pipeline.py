import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("07_LOGS/cips_execution.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

class CIPSPipelineOrchestrator:
    def __init__(self, project_name: str, niche: str, topic: str):
        self.project_name = project_name
        self.niche = niche
        self.topic = topic
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.output_dir = Path(f"05_OUTPUTS/youtube/{self.timestamp}")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def execute_stage_1_research(self) -> dict:
        logging.info("--> [Etapa 1/4] Ejecutando Director de Investigación...")
        research_data = {
            "topic": self.topic,
            "niche": self.niche,
            "angle": "Controversia/Mito vs Realidad para enganchar en TikTok",
            "key_points": [
                "Gancho directo en los primeros 3 segundos",
                "Datos científicos traducidos a lenguaje simple",
                "Llamado a la acción claro"
            ]
        }
        
        file_path = self.output_dir / "research.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# Investigación: {self.topic}\n\n")
            f.write(json.dumps(research_data, indent=2, ensure_ascii=False))
            
        return research_data

    def execute_stage_2_script(self, research: dict) -> str:
        logging.info("--> [Etapa 2/4] Generando Guión Viral (TikTok / Shorts)...")
        script_content = f"""# GUIÓN VIRAL TIKTOK / SHORTS
**Tema:** {self.topic}
**Formato:** 60 Segundos

---
[00:00 - 00:03] GANCHO VISUAL & AUDITIVO:
"¿Sabías que el 90% de las personas cometen este error con la IA sin darse cuenta?"

[00:03 - 00:15] EL PROBLEMA:
La mayoría cree que necesita herramientas caras, pero hoy te revelo cómo orquestar agentes gratis.

[00:15 - 00:45] LA SOLUCIÓN / PASOS:
1. Usa arquitecturas multi-agente locales.
2. Integra Ollama o modelos open-source.
3. Automatiza la salida en archivos Markdown interactivos.

[00:45 - 00:60] CTA / CONCLUSIÓN:
"Comenta 'AGENTE' y te enseño el flujo paso a paso. Sígueme para más."
"""
        file_path = self.output_dir / "script.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(script_content)
            
        return script_content

    def execute_stage_3_storyboard_and_prompts(self, script: str):
        logging.info("--> [Etapa 3/4] Creando Storyboard y Prompts Visuales...")
        storyboard = """# STORYBOARD & VISUAL PROMPTS

| Segundo | Escena | Prompt Imagen/Video (Midjourney/Leonardo/Pika) |
|---|---|---|
| 00:00 - 00:03 | Primer plano de pantalla futurista con código cayendo estilo Matrix | Cinematic photo, hacker room, neon glowing blue code, 8k --ar 9:16 |
| 00:03 - 00:15 | Humano frustrado frente a una computadora | Photorealistic, stressed developer in front of glowing monitors, moody lighting --ar 9:16 |
| 00:15 - 00:45 | Diagrama 3D de red neuronal interactuando | Abstract 3D nodes connecting, digital network visualization, highly detailed --ar 9:16 |
"""
        with open(self.output_dir / "storyboard.md", "w", encoding="utf-8") as f:
            f.write(storyboard)

    def execute_stage_4_seo_and_publishing(self):
        logging.info("--> [Etapa 4/4] Generando Metadatos SEO e Instrucciones de Publicación...")
        seo_data = f"""# SEO & METADATOS TIKTOK

**Título:** Cómo crear un Consejo de Expertos IA a Costo $0 🚀
**Descripción:** Automatiza tus proyectos usando orquestación multi-agente gratis.
**Hashtags:** #ArtificialIntelligence #Python #Ollama #TikTokTech #Automation #TechTips
"""
        with open(self.output_dir / "publication.md", "w", encoding="utf-8") as f:
            f.write(seo_data)

    def run_pipeline(self):
        logging.info(f"=== INICIANDO PIPELINE CIPS V5: {self.project_name} ===")
        res = self.execute_stage_1_research()
        script = self.execute_stage_2_script(res)
        self.execute_stage_3_storyboard_and_prompts(script)
        self.execute_stage_4_seo_and_publishing()
        logging.info(f"=== PIPELINE FINALIZADO CON ÉXITO ===")
        logging.info(f"Artefactos listos en: {self.output_dir.resolve()}")

if __name__ == "__main__":
    orchestrator = CIPSPipelineOrchestrator(
        project_name="PROYECTO_TIKTOK_0001",
        niche="Inteligencia Artificial y Automatización",
        topic="Creación de un Consejo de IA Multi-agente en Local a Costo $0"
    )
    orchestrator.run_pipeline()