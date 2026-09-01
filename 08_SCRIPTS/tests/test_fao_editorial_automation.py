from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import project_manager as project_manager_module  # noqa: E402
from editorial_context import EditorialContextEngine  # noqa: E402
from editorial_contract import EDITORIAL_STAGES, canonical_editorial_path  # noqa: E402
from editorial_validator import EditorialValidatorEngine  # noqa: E402
from llm_provider import LLMProvider, ProviderResult  # noqa: E402
from manual_llm_provider import ManualLLMProvider  # noqa: E402
from pipeline_engine import PipelineEngine  # noqa: E402
from project_manager import ProjectManager  # noqa: E402
from runtime_context import RuntimeContext  # noqa: E402
from runtime_models import (  # noqa: E402
    ContextObject,
    LLMResponse,
    Project,
    ValidationResult,
)


@pytest.fixture
def isolated_projects(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    projects_dir = tmp_path / "04_PROYECTOS"
    monkeypatch.setattr(project_manager_module, "PROJECTS_DIR", projects_dir)
    return projects_dir


class _EditorialProvider(LLMProvider):
    provider_name = "fao_test_provider"
    model_name = "deterministic-editorial-v1"

    def __init__(self) -> None:
        self.stages: list[str] = []
        self.prompts: dict[str, str] = {}

    def generate(self, prompt: str, metadata: dict | None = None) -> ProviderResult:
        stage = str((metadata or {}).get("stage", ""))
        self.stages.append(stage)
        self.prompts[stage] = prompt
        content = _VALID_CONTENT[stage]
        return ProviderResult.ok(
            response=LLMResponse(
                content=content,
                model=self.model_name,
                metadata={
                    "provider": self.provider_name,
                    "mode": "automatic",
                },
            ),
            metadata={
                "provider": self.provider_name,
                "model": self.model_name,
            },
        )


_VALID_CONTENT = {
    "investigacion": """# RESUMEN

Un eclipse solar ocurre cuando la Luna pasa entre la Tierra y el Sol y proyecta su sombra sobre una parte limitada de la superficie terrestre. [A1] La alineación debe ser suficientemente precisa y sucede cerca de la fase de luna nueva. El fenómeno no cubre todo el planeta al mismo tiempo porque la umbra lunar forma una franja relativamente estrecha. [A2] Dentro de esa franja puede observarse totalidad, mientras que zonas más amplias reciben penumbra y ven un eclipse parcial. La geometría cambia de un evento a otro por las órbitas y distancias aparentes.

La duración local depende de la trayectoria de la sombra y de la posición del observador. Mirar directamente el Sol fuera de la breve totalidad puede dañar los ojos. La explicación debe distinguir la mecánica astronómica de las recomendaciones de seguridad y evitar promesas sobre lo que verá una persona sin conocer su ubicación.

# EVIDENCIA

- [A1] La alineación Sol-Luna-Tierra y su relación con la luna nueva están descritas por [F1] y [F2].
- [A2] La diferencia entre umbra, penumbra, totalidad y parcialidad está respaldada por [F1] y [F2].

Las dos fuentes explican el mismo mecanismo con enfoques educativos independientes. La coincidencia permite formular un guion breve sin convertir detalles variables, como duración o visibilidad local, en reglas universales. La localización y el calendario deben tratarse como datos específicos de cada evento y no como afirmaciones generales.

# RIESGOS

No debe afirmarse que todos los eclipses son totales ni que pueden verse desde cualquier lugar. Tampoco debe recomendarse observar el Sol sin protección certificada. Los horarios, trayectorias y porcentajes de cobertura cambian, de modo que cualquier dato local necesita una fuente oficial correspondiente al evento. La incertidumbre principal del contenido breve es cuánto detalle geométrico cabe sin perder claridad.

# FUENTES

- [F1] Solar Eclipses | NASA Science | https://science.nasa.gov/eclipses/
- [F2] Eclipses and the Moon | Royal Museums Greenwich | https://www.rmg.co.uk/stories/topics/solar-lunar-eclipses

Ambas referencias identifican responsables institucionales y rutas completas para auditoría posterior. El entregable conserva los identificadores para que la verificación pueda aceptar, rechazar o limitar cada afirmación sin perder su procedencia.
""",
    "verificacion": """# VERIFICACIÓN

| Afirmación | Estado | Fuentes | Justificación |
|---|---|---|---|
| [A1] | APROBADA | [F1], [F2] | Ambas fuentes describen la alineación entre el Sol, la Luna y la Tierra cerca de la luna nueva. |
| [A2] | APROBADA | [F1], [F2] | Las referencias distinguen umbra, penumbra y las zonas de observación total o parcial. |

La revisión conserva la escala correcta: la sombra recorre regiones concretas y no cubre el planeta completo al mismo tiempo. También separa la explicación geométrica de la seguridad ocular. No se aprueban horarios, ciudades, duración máxima ni porcentaje de cobertura porque esos valores dependen del eclipse específico y no aparecen como parte de las afirmaciones generales evaluadas.

# EVIDENCIA

[A1] es coherente con la explicación orbital de [F1] y con el material educativo de [F2]. [A2] está sustentada por las descripciones coincidentes de sombra central y sombra parcial en [F1] y [F2]. La doble referencia reduce el riesgo de depender de una sola formulación. La verificación se limita al contenido necesario para explicar el mecanismo en un video corto.

# LIMITACIONES

Las fuentes permiten explicar el fenómeno general, pero no determinan lo que verá una audiencia en una fecha o ubicación desconocida. Una pieza futura sobre un eclipse concreto deberá añadir efemérides y mapas oficiales. La seguridad ocular requiere instrucciones específicas y productos certificados; este paquete sólo debe recordar que mirar el Sol sin protección adecuada es peligroso.

# CONCLUSIÓN

Las afirmaciones [A1] y [A2] quedan aprobadas para el guion. El contenido puede explicar alineación, sombra, totalidad y parcialidad sin introducir predicciones locales. Cualquier dato adicional permanecerá fuera del guion hasta contar con evidencia identificada y verificable.
""",
    "guion": """# GUION

## GANCHO

Durante unos minutos, el día puede parecer noche. Pero el Sol no se apaga: una sombra está cruzando la Tierra.

## DESARROLLO

Un eclipse solar ocurre cuando la Luna se alinea entre nuestro planeta y el Sol cerca de la luna nueva. Esa alineación bloquea parte de la luz y proyecta dos zonas de sombra. En la franja central, la Luna puede cubrir por completo el disco solar y el eclipse se ve total. Alrededor, la penumbra sólo tapa una parte y el eclipse se observa parcial. [A1]

La sombra se desplaza sobre regiones específicas, por eso dos personas en lugares distintos pueden ver experiencias muy diferentes durante el mismo evento. [A2] La ubicación importa tanto como la alineación. Fuera de la totalidad, mirar directamente el Sol sin protección adecuada puede dañar los ojos.

## CIERRE

Así que un eclipse no es un Sol que desaparece: es la geometría precisa de tres mundos y una sombra en movimiento. Consulta siempre información oficial para tu ubicación antes de observarlo.

## LLAMADA A LA ACCIÓN

Guarda esta explicación y compártela con alguien que quiera entender el próximo eclipse sin mitos.

## TRAZABILIDAD

- La alineación y la luna nueva se apoyan en [A1].
- Las zonas de sombra y la visibilidad regional se apoyan en [A2].
""",
    "storyboard": """# STORYBOARD

## ESCENA 1

- Duración: 10 s
- Visual: El cielo diurno se oscurece sobre un paisaje mientras aparece la silueta de la Luna frente al Sol.
- Locución: Durante unos minutos, el día puede parecer noche, aunque el Sol no se apaga.
- Evidencia: [A1]

La apertura debe comunicar sorpresa sin sensacionalismo. El encuadre vertical conserva el Sol en la zona superior y deja espacio inferior para subtítulos canónicos.

## ESCENA 2

- Duración: 10 s
- Visual: Diagrama limpio de la alineación Sol, Luna y Tierra con la Luna situada entre ambos cuerpos.
- Locución: El eclipse ocurre cuando la Luna se alinea entre la Tierra y el Sol cerca de la luna nueva.
- Evidencia: [A1]

Los tamaños pueden ser esquemáticos, pero las posiciones relativas deben ser inequívocas y no deben sugerir que la Luna emite luz.

## ESCENA 3

- Duración: 10 s
- Visual: La umbra y la penumbra llegan a regiones diferentes de la superficie terrestre con contraste claro.
- Locución: La sombra central permite ver totalidad y la zona exterior produce un eclipse parcial.
- Evidencia: [A2]

La imagen prioriza comprensión y muestra que la franja central es menor que la región de eclipse parcial. No se añaden ciudades ni fechas.

## ESCENA 4

- Duración: 10 s
- Visual: Dos observadores en ubicaciones distintas ven coberturas diferentes y aparece un recordatorio visual de protección ocular.
- Locución: Tu ubicación cambia la experiencia; consulta información oficial y protege siempre tus ojos.
- Evidencia: [A2]

El cierre combina escala geográfica y una recomendación prudente. La transición final regresa a la alineación para reforzar la idea de geometría y sombra en movimiento.
""",
    "seo": """# TÍTULO

¿Cómo funciona un eclipse solar? La sombra de la Luna explicada

# DESCRIPCIÓN

Descubre por qué el día puede oscurecerse durante un eclipse solar. Esta explicación visual muestra la alineación entre el Sol, la Luna y la Tierra, y aclara la diferencia entre la franja de totalidad y las zonas donde el eclipse se ve parcial. El contenido está pensado para una audiencia general y recuerda consultar información oficial para cada ubicación.

# PALABRAS CLAVE

eclipse solar, cómo funciona un eclipse, sombra de la Luna, alineación Sol Luna Tierra, eclipse total, eclipse parcial, umbra y penumbra, astronomía básica

# HASHTAGS

#EclipseSolar #Astronomía #Ciencia #Luna #AprendeEnSegundos #YouTubeShorts

# ETIQUETAS

Educación científica, explicación visual, fenómenos astronómicos, espacio, observación segura. El conjunto evita promesas y se mantiene alineado con el guion verificado.
""",
    "publicacion": """# PUBLICACIÓN

## PLATAFORMA

YouTube Shorts, formato vertical y dirigido a público general interesado en ciencia accesible.

## FORMATO

Video educativo de 40 segundos con narración clara, cuatro escenas, subtítulos inferiores y cierre responsable. El paquete no contiene una orden de envío a la plataforma.

## COPY

¿Por qué el día puede oscurecerse durante un eclipse solar? La Luna proyecta una sombra sobre regiones concretas de la Tierra. En la zona central puede verse totalidad; alrededor, el eclipse es parcial. La ubicación cambia lo que observas, así que consulta siempre información oficial antes del evento.

## HASHTAGS

#EclipseSolar #Astronomía #Ciencia #Luna #AprendeEnSegundos #YouTubeShorts

## CONTROL DE PUBLICACIÓN

publication_performed: false

authorization_required: true

La preparación editorial no equivale a publicación. Cualquier acción futura requiere una autorización humana explícita e independiente, y debe preservar las fuentes, los créditos y la evidencia de revisión.
""",
    "narracion": """Durante unos minutos, el día puede parecer noche, pero el Sol no se apaga. Un eclipse solar ocurre cuando la Luna se alinea entre la Tierra y el Sol y proyecta su sombra sobre regiones concretas. En la franja central, el disco solar puede quedar cubierto por completo; alrededor, sólo se oculta una parte. Por eso dos personas en lugares distintos pueden observar experiencias diferentes. Es geometría, luz y una sombra en movimiento. Consulta información oficial para tu ubicación y protege siempre tus ojos al observar el Sol.""",
}


def _created_project(isolated_projects: Path) -> tuple[ProjectManager, Path]:
    manager = ProjectManager()
    created = manager.create_project(
        "Cómo funcionan los eclipses solares",
        plataforma="YouTube Shorts",
        duracion_segundos=40,
        audiencia="público general",
        estilo_creativo="científico, visual y accesible",
    )
    return manager, Path(created["path"])


def _direct_context(
    project_path: Path,
    stage: str,
    content: str,
) -> RuntimeContext:
    project = ProjectManager().load_project(project_path)
    project.stage_actual = stage
    path = canonical_editorial_path(project_path, stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    context = RuntimeContext(project=project)
    context.llm_response = LLMResponse(
        content=content,
        model="direct-test",
        metadata={"provider": "test", "mode": "automatic"},
    )
    context.validation_result = ValidationResult(
        approved=True,
        metadata={"score": 100, "passing_score": 70},
    )
    return context


def test_context_includes_request_and_only_required_approved_inputs(
    isolated_projects: Path,
) -> None:
    _, project_path = _created_project(isolated_projects)
    research_path = canonical_editorial_path(project_path, "investigacion")
    research_path.parent.mkdir(parents=True, exist_ok=True)
    research_path.write_text(_VALID_CONTENT["investigacion"], encoding="utf-8")
    project = ProjectManager().load_project(project_path)
    project.stage_actual = "verificacion"
    context = RuntimeContext(project=project)
    context.context_object = ContextObject(project=project, modules=[], content="CORE")

    result = EditorialContextEngine().execute(context)

    assert result.success, result.errors
    assert "Cómo funcionan los eclipses solares" in context.context_object.content
    assert "ENTREGABLE APROBADO — INVESTIGACION" in context.context_object.content
    assert "publication_performed" not in context.context_object.content
    assert context.metadata["editorial_inputs"][0]["stage"] == "investigacion"


def test_research_without_two_traceable_urls_is_rejected(
    isolated_projects: Path,
) -> None:
    _, project_path = _created_project(isolated_projects)
    invalid = _VALID_CONTENT["investigacion"].replace(
        "https://www.rmg.co.uk/stories/topics/solar-lunar-eclipses",
        "fuente-sin-url",
    )
    context = _direct_context(project_path, "investigacion", invalid)

    result = EditorialValidatorEngine().execute(context)

    assert result.success is False
    assert any("dos fuentes" in error for error in result.errors)


def test_verification_rejects_unknown_source_reference(
    isolated_projects: Path,
) -> None:
    _, project_path = _created_project(isolated_projects)
    research = canonical_editorial_path(project_path, "investigacion")
    research.parent.mkdir(parents=True, exist_ok=True)
    research.write_text(_VALID_CONTENT["investigacion"], encoding="utf-8")
    invalid = _VALID_CONTENT["verificacion"].replace("[F2] |", "[F9] |", 1)
    context = _direct_context(project_path, "verificacion", invalid)

    result = EditorialValidatorEngine().execute(context)

    assert result.success is False
    assert any("fuentes inexistentes" in error for error in result.errors)


def test_storyboard_blocks_duration_that_disagrees_with_request(
    isolated_projects: Path,
) -> None:
    _, project_path = _created_project(isolated_projects)
    for stage in ("investigacion", "verificacion", "guion"):
        path = canonical_editorial_path(project_path, stage)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_VALID_CONTENT[stage], encoding="utf-8")
    invalid = _VALID_CONTENT["storyboard"].replace("Duración: 10 s", "Duración: 9 s", 1)
    context = _direct_context(project_path, "storyboard", invalid)

    result = EditorialValidatorEngine().execute(context)

    assert result.success is False
    assert any("suman 39 s" in error for error in result.errors)


def test_manual_provider_remains_an_explicit_pause() -> None:
    result = ManualLLMProvider().generate("Prompt editorial válido")

    assert result.success is False
    assert result.metadata["requires_user_action"] is True
    assert result.response is None


def test_legacy_project_without_operational_request_keeps_previous_contract(
    tmp_path: Path,
) -> None:
    project = Project(
        project_id="PROYECTO_HEREDADO",
        path=tmp_path,
        tema="Tema heredado",
        stage_actual="guion",
    )
    context = RuntimeContext(project=project)
    context.context_object = ContextObject(project=project, modules=[], content="CORE")
    context.llm_response = LLMResponse(content="Contenido histórico válido.")
    context.validation_result = ValidationResult(approved=True)

    context_result = EditorialContextEngine().execute(context)
    validation_result = EditorialValidatorEngine().execute(context)

    assert context_result.success and validation_result.success
    assert context_result.metadata["legacy_project"] is True
    assert validation_result.metadata["legacy_project"] is True
    assert context.context_object.content == "CORE"


def test_full_editorial_chain_uses_configured_provider_and_builds_evidence(
    isolated_projects: Path,
) -> None:
    _, project_path = _created_project(isolated_projects)
    provider = _EditorialProvider()
    pipeline = PipelineEngine(stage_delay_seconds=0)
    pipeline.llm_adapter.set_provider(provider)

    results = []
    for expected_stage in EDITORIAL_STAGES:
        project = ProjectManager().load_project(project_path)
        assert project.stage_actual == expected_stage
        result = pipeline.execute(project_path=project_path)
        results.append(result)
        assert result.success, result.errors
        assert result.metadata["completed_stage"] == expected_stage
        assert result.metadata["validation_approved"] is True
        assert result.metadata["response_persisted"] is True

    assert provider.stages == list(EDITORIAL_STAGES)
    assert ProjectManager().load_project(project_path).stage_actual == "voz"
    assert "SOLICITUD OPERATIVA AUTORITATIVA" in provider.prompts["investigacion"]
    assert "ENTREGABLE APROBADO — INVESTIGACION" in provider.prompts["verificacion"]
    assert "texto plano UTF-8" in provider.prompts["narracion"]

    ledger_path = project_path / "state" / "editorial_evidence.json"
    package_path = project_path / "state" / "editorial_package.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    package = json.loads(package_path.read_text(encoding="utf-8"))

    assert ledger["schema_name"] == "cips.fao.editorial_evidence"
    assert list(ledger["stages"]) == list(EDITORIAL_STAGES)
    assert all(
        item["provider"] == provider.provider_name
        and item["manual_fallback"] is False
        and item["publication_performed"] is False
        for item in ledger["stages"].values()
    )
    assert package["schema_name"] == "cips.fao.editorial_package"
    assert package["status"] == "editorial_complete"
    assert package["artifact_count"] == len(EDITORIAL_STAGES)
    assert package["placeholder_files"] == []
    assert package["publication_performed"] is False
    assert results[-1].metadata["next_stage"] == "voz"

    for stage in EDITORIAL_STAGES:
        content = canonical_editorial_path(project_path, stage).read_text(
            encoding="utf-8"
        )
        assert "\nPendiente\n" not in content


def test_evidence_write_is_idempotent_for_identical_content(
    isolated_projects: Path,
) -> None:
    _, project_path = _created_project(isolated_projects)
    content = _VALID_CONTENT["investigacion"]
    validator = EditorialValidatorEngine()

    first = validator.execute(_direct_context(project_path, "investigacion", content))
    first_ledger = json.loads(
        (project_path / "state" / "editorial_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    second = validator.execute(_direct_context(project_path, "investigacion", content))
    second_ledger = json.loads(
        (project_path / "state" / "editorial_evidence.json").read_text(
            encoding="utf-8"
        )
    )

    assert first.success and second.success
    assert first_ledger == second_ledger


def test_new_workspace_markdown_has_no_pending_placeholder(
    isolated_projects: Path,
) -> None:
    _, project_path = _created_project(isolated_projects)

    markdown_files = list(project_path.glob("*.md"))
    assert markdown_files
    assert all("Pendiente" not in path.read_text(encoding="utf-8") for path in markdown_files)
