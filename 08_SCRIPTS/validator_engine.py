"""
=========================================================
Proyecto : CIPS
Release  : 0.6
Build    : 040
Archivo  : validator_engine.py
Estado   : RELEASE
=========================================================

Valida:

- estructura general de CIPS;
- estructura de proyectos;
- respuestas producidas por modelos de IA;
- longitud y completitud;
- encabezados requeridos;
- cumplimiento de restricciones;
- calidad básica;
- posibles respuestas truncadas.

Compatibilidad:
- Validator legado utilizado por MenuController.
- PipelineEngine mediante execute(Project, LLMResponse).
- PipelineRunner mediante execute(RuntimeContext).
"""

from pathlib import Path
import re
import unicodedata

from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import (
    EngineResult,
    LLMResponse,
    Project,
    ValidationResult,
)
from utils import ROOT, read_yaml


VALIDATION_RULES_PATH = (
    ROOT
    / "01_CONFIG"
    / "validation_rules.yaml"
)


REQUIRED_ROOT_FOLDERS = [
    "00_DOCUMENTACION",
    "01_CONFIG",
    "02_PROMPTS",
    "03_PLANTILLAS",
    "04_PROYECTOS",
    "05_OUTPUTS",
    "06_MEMORIA",
    "07_LOGS",
    "08_SCRIPTS",
    "09_KNOWLEDGE",
    "CIPS",
]


class Validator:
    """
    Validador estructural del sistema.

    Se conserva para la interfaz actual y para las pruebas
    generales de carpetas, archivos y proyectos.
    """

    def validate_system(self) -> list[str]:
        """
        Verifica la estructura mínima de CIPS.
        """

        errors: list[str] = []

        for folder in REQUIRED_ROOT_FOLDERS:
            if not (ROOT / folder).exists():
                errors.append(
                    f"Falta carpeta raíz: {folder}"
                )

        required_files = [
            ROOT / "PROJECT_MANIFEST.yaml",
            ROOT / "requirements.txt",
            ROOT / "01_CONFIG" / "config_global.yaml",
            ROOT / "01_CONFIG" / "pipeline.yaml",
            ROOT / "01_CONFIG" / "llm.yaml",
            VALIDATION_RULES_PATH,
        ]

        for file_path in required_files:
            if not file_path.exists():
                errors.append(
                    f"Falta archivo requerido: {file_path}"
                )

        return errors

    def validate_project(
        self,
        project_path: Path,
    ) -> list[str]:
        """
        Verifica la estructura mínima de un proyecto.
        """

        errors: list[str] = []

        required_files = [
            "proyecto.yaml",
            "memoria.yaml",
            "CONTEXTO.md",
            "00_TEMA.md",
            "01_INVESTIGACION.md",
            "02_VERIFICACION.md",
            "03_GUION.md",
            "04_STORYBOARD.md",
            "05_SEO.md",
            "06_PUBLICACION.md",
            "07_FINAL.md",
        ]

        for filename in required_files:
            if not (project_path / filename).exists():
                errors.append(
                    f"Falta archivo en proyecto: {filename}"
                )

        project_yaml = read_yaml(
            project_path / "proyecto.yaml"
        )

        if not project_yaml.get("id"):
            errors.append(
                "proyecto.yaml no tiene ID"
            )

        if not project_yaml.get("tema"):
            errors.append(
                "proyecto.yaml no tiene tema"
            )

        if not project_yaml.get("estado"):
            errors.append(
                "proyecto.yaml no tiene estado"
            )

        return errors


class ValidatorEngine(RuntimeComponent):
    """
    Validador profesional de respuestas IA.

    Calcula una puntuación de 0 a 100 utilizando:

    - longitud;
    - estructura;
    - completitud;
    - cumplimiento de restricciones;
    - calidad básica.

    Una respuesta únicamente se aprueba si:

    - supera la puntuación mínima;
    - no está vacía;
    - no parece truncada;
    - no contiene filtración grave del prompt;
    - cumple los mínimos del Stage.
    """

    component_name = "validator_engine"

    DEFAULT_PASSING_SCORE = 70

    def execute(
        self,
        runtime_input: Project | RuntimeContext,
        response: LLMResponse | None = None,
    ) -> EngineResult:
        """
        Valida la respuesta del Stage actual.
        """

        try:
            runtime_context = self._get_runtime_context(
                runtime_input
            )

            project = self._get_project(
                runtime_input
            )

            llm_response = self._get_llm_response(
                runtime_input=runtime_input,
                response=response,
            )

            if llm_response is None:
                return EngineResult.fail(
                    message=(
                        "No existe una respuesta LLM "
                        "disponible para validar."
                    ),
                    errors=[
                        "LLMResponse no disponible."
                    ],
                    metadata=self._base_metadata(project),
                )

            rules = self._load_rules()

            content = (
                llm_response.content
                or ""
            ).strip()

            stage_rules = self._get_stage_rules(
                rules=rules,
                stage=project.stage_actual,
            )

            errors: list[str] = []
            warnings: list[str] = []
            observations: list[str] = []

            analysis = self._analyze_content(
                content=content,
                rules=rules,
                stage_rules=stage_rules,
                errors=errors,
                warnings=warnings,
                observations=observations,
            )

            scores = self._calculate_scores(
                content=content,
                rules=rules,
                stage_rules=stage_rules,
                analysis=analysis,
            )

            total_score = scores["total"]
            passing_score = self._get_passing_score(
                rules
            )

            if total_score < passing_score:
                errors.append(
                    "La respuesta no alcanzó la puntuación "
                    f"mínima: {total_score}/{passing_score}."
                )

            approved = not errors

            metadata = {
                **self._base_metadata(project),
                "model": llm_response.model,
                "approved": approved,
                "score": total_score,
                "passing_score": passing_score,
                "scores": scores,
                "characters": analysis["characters"],
                "words": analysis["words"],
                "sentences": analysis["sentences"],
                "headings": analysis["headings"],
                "required_headings": analysis[
                    "required_headings"
                ],
                "missing_required_headings": analysis[
                    "missing_required_headings"
                ],
                "recommended_headings": analysis[
                    "recommended_headings"
                ],
                "present_recommended_headings": analysis[
                    "present_recommended_headings"
                ],
                "truncated": analysis["truncated"],
                "prompt_leakage": analysis[
                    "prompt_leakage"
                ],
                "repetition_ratio": analysis[
                    "repetition_ratio"
                ],
                "warnings_count": len(warnings),
                "errors_count": len(errors),
                "rules_path": str(
                    VALIDATION_RULES_PATH
                ),
            }

            validation_result = ValidationResult(
                approved=approved,
                observations=observations,
                warnings=warnings,
                errors=errors,
                metadata=metadata,
            )

            if runtime_context is not None:
                runtime_context.validation_result = (
                    validation_result
                )

            if not approved:
                return EngineResult.fail(
                    message=(
                        "La respuesta no superó la "
                        "validación profesional."
                    ),
                    errors=errors,
                    warnings=warnings,
                    metadata=metadata,
                )

            if runtime_context is not None:
                return EngineResult.ok(
                    data=runtime_context,
                    message=(
                        "Respuesta validada y aprobada "
                        f"con puntuación {total_score}/100."
                    ),
                    warnings=warnings,
                    metadata=metadata,
                )

            return EngineResult.ok(
                data=validation_result,
                message=(
                    "Respuesta validada y aprobada "
                    f"con puntuación {total_score}/100."
                ),
                warnings=warnings,
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en ValidatorEngine."
                ),
                errors=[str(error)],
                metadata={
                    "component": self.component_name,
                },
            )

    def _analyze_content(
        self,
        content: str,
        rules: dict,
        stage_rules: dict,
        errors: list[str],
        warnings: list[str],
        observations: list[str],
    ) -> dict:
        """
        Ejecuta todas las comprobaciones del contenido.
        """

        general = rules.get(
            "general",
            {},
        )

        quality_rules = rules.get(
            "quality",
            {},
        )

        characters = len(content)
        words = self._count_words(content)
        sentences = self._count_sentences(content)
        headings = self._extract_headings(content)

        minimum_characters = self._safe_int(
            stage_rules.get(
                "minimum_characters",
                general.get(
                    "minimum_characters",
                    300,
                ),
            ),
            default=300,
        )

        minimum_words = self._safe_int(
            stage_rules.get(
                "minimum_words",
                general.get(
                    "minimum_words",
                    50,
                ),
            ),
            default=50,
        )

        required_headings = self._normalize_list(
            stage_rules.get(
                "required_headings",
                [],
            )
        )

        recommended_headings = self._normalize_list(
            stage_rules.get(
                "recommended_headings",
                [],
            )
        )

        normalized_headings = {
            self._normalize_text(heading)
            for heading in headings
        }

        missing_required_headings = [
            heading
            for heading in required_headings
            if not self._heading_is_present(
                heading=heading,
                normalized_headings=normalized_headings,
            )
        ]

        present_recommended_headings = [
            heading
            for heading in recommended_headings
            if self._heading_is_present(
                heading=heading,
                normalized_headings=normalized_headings,
            )
        ]

        truncated = self._is_truncated(
            content=content,
            rules=rules,
        )

        prompt_leakage = self._contains_markers(
            content=content,
            markers=(
                rules.get(
                    "model_text",
                    {},
                ).get(
                    "prompt_leakage_markers",
                    [],
                )
            ),
        )

        refusal_detected = self._contains_markers(
            content=content,
            markers=(
                rules.get(
                    "model_text",
                    {},
                ).get(
                    "refusal_markers",
                    [],
                )
            ),
        )

        generic_text_detected = self._contains_markers(
            content=content,
            markers=(
                rules.get(
                    "model_text",
                    {},
                ).get(
                    "generic_markers",
                    [],
                )
            ),
        )

        sensationalism_detected = self._contains_markers(
            content=content,
            markers=quality_rules.get(
                "sensationalism_markers",
                [],
            ),
        )

        repetition_ratio = (
            self._calculate_repetition_ratio(
                content
            )
        )

        minimum_sentence_count = self._safe_int(
            quality_rules.get(
                "minimum_sentence_count",
                3,
            ),
            default=3,
        )

        if not content:
            errors.append(
                "La respuesta está vacía."
            )

        if characters < minimum_characters:
            errors.append(
                "La respuesta es demasiado corta: "
                f"{characters} caracteres; mínimo requerido: "
                f"{minimum_characters}."
            )

        if words < minimum_words:
            errors.append(
                "La respuesta contiene pocas palabras: "
                f"{words}; mínimo requerido: {minimum_words}."
            )

        if sentences < minimum_sentence_count:
            errors.append(
                "La respuesta no contiene suficientes "
                f"oraciones completas: {sentences}; "
                f"mínimo requerido: {minimum_sentence_count}."
            )

        if missing_required_headings:
            errors.append(
                "Faltan encabezados obligatorios: "
                + ", ".join(
                    missing_required_headings
                )
                + "."
            )

        if (
            truncated
            and general.get(
                "reject_truncated_response",
                True,
            )
        ):
            errors.append(
                "La respuesta parece truncada o incompleta."
            )

        if (
            prompt_leakage
            and general.get(
                "reject_prompt_leakage",
                True,
            )
        ):
            errors.append(
                "La respuesta contiene posibles "
                "instrucciones internas del prompt."
            )

        if refusal_detected:
            warnings.append(
                "La respuesta puede contener una "
                "negativa del modelo IA."
            )

        if generic_text_detected:
            warnings.append(
                "La respuesta contiene texto genérico "
                "asociado al modelo IA."
            )

        if sensationalism_detected:
            warnings.append(
                "La respuesta contiene lenguaje "
                "potencialmente sensacionalista."
            )

        repetition_threshold = self._safe_float(
            quality_rules.get(
                "excessive_repetition_threshold",
                0.35,
            ),
            default=0.35,
        )

        if repetition_ratio > repetition_threshold:
            warnings.append(
                "La respuesta presenta repetición "
                "excesiva de contenido."
            )

        missing_recommended = [
            heading
            for heading in recommended_headings
            if heading not in present_recommended_headings
        ]

        if missing_recommended:
            observations.append(
                "Encabezados recomendados ausentes: "
                + ", ".join(missing_recommended)
                + "."
            )

        return {
            "characters": characters,
            "words": words,
            "sentences": sentences,
            "headings": headings,
            "minimum_characters": minimum_characters,
            "minimum_words": minimum_words,
            "required_headings": required_headings,
            "missing_required_headings": (
                missing_required_headings
            ),
            "recommended_headings": (
                recommended_headings
            ),
            "present_recommended_headings": (
                present_recommended_headings
            ),
            "truncated": truncated,
            "prompt_leakage": prompt_leakage,
            "refusal_detected": refusal_detected,
            "generic_text_detected": (
                generic_text_detected
            ),
            "sensationalism_detected": (
                sensationalism_detected
            ),
            "repetition_ratio": repetition_ratio,
            "minimum_sentence_count": (
                minimum_sentence_count
            ),
        }

    def _calculate_scores(
        self,
        content: str,
        rules: dict,
        stage_rules: dict,
        analysis: dict,
    ) -> dict[str, int]:
        """
        Calcula puntuaciones ponderadas de 0 a 100.
        """

        weights = rules.get(
            "weights",
            {},
        )

        length_weight = self._safe_int(
            weights.get("length", 15),
            default=15,
        )

        structure_weight = self._safe_int(
            weights.get("structure", 25),
            default=25,
        )

        completeness_weight = self._safe_int(
            weights.get("completeness", 25),
            default=25,
        )

        restrictions_weight = self._safe_int(
            weights.get("restrictions", 20),
            default=20,
        )

        quality_weight = self._safe_int(
            weights.get("quality", 15),
            default=15,
        )

        length_score = self._score_length(
            analysis=analysis,
            weight=length_weight,
        )

        structure_score = self._score_structure(
            analysis=analysis,
            weight=structure_weight,
        )

        completeness_score = self._score_completeness(
            analysis=analysis,
            weight=completeness_weight,
        )

        restrictions_score = self._score_restrictions(
            analysis=analysis,
            weight=restrictions_weight,
        )

        quality_score = self._score_quality(
            content=content,
            analysis=analysis,
            weight=quality_weight,
        )

        raw_total = (
            length_score
            + structure_score
            + completeness_score
            + restrictions_score
            + quality_score
        )

        maximum_total = (
            length_weight
            + structure_weight
            + completeness_weight
            + restrictions_weight
            + quality_weight
        )

        if maximum_total <= 0:
            total = 0
        else:
            total = round(
                raw_total
                / maximum_total
                * 100
            )

        total = max(
            0,
            min(
                total,
                100,
            ),
        )

        return {
            "length": length_score,
            "structure": structure_score,
            "completeness": completeness_score,
            "restrictions": restrictions_score,
            "quality": quality_score,
            "raw_total": raw_total,
            "maximum_total": maximum_total,
            "total": total,
        }

    def _score_length(
        self,
        analysis: dict,
        weight: int,
    ) -> int:
        """
        Puntúa caracteres y palabras requeridos.
        """

        character_ratio = self._safe_ratio(
            analysis["characters"],
            analysis["minimum_characters"],
        )

        word_ratio = self._safe_ratio(
            analysis["words"],
            analysis["minimum_words"],
        )

        ratio = min(
            character_ratio,
            word_ratio,
            1.0,
        )

        return round(
            weight * ratio
        )

    def _score_structure(
        self,
        analysis: dict,
        weight: int,
    ) -> int:
        """
        Puntúa encabezados obligatorios y recomendados.
        """

        required = analysis[
            "required_headings"
        ]

        missing = analysis[
            "missing_required_headings"
        ]

        recommended = analysis[
            "recommended_headings"
        ]

        present_recommended = analysis[
            "present_recommended_headings"
        ]

        if required:
            required_ratio = (
                len(required) - len(missing)
            ) / len(required)
        else:
            required_ratio = 1.0

        if recommended:
            recommended_ratio = (
                len(present_recommended)
                / len(recommended)
            )
        else:
            recommended_ratio = 1.0

        combined_ratio = (
            required_ratio * 0.8
            + recommended_ratio * 0.2
        )

        return round(
            weight * combined_ratio
        )

    def _score_completeness(
        self,
        analysis: dict,
        weight: int,
    ) -> int:
        """
        Puntúa completitud y cierre adecuado.
        """

        score = weight

        if analysis["truncated"]:
            score -= round(
                weight * 0.7
            )

        if (
            analysis["sentences"]
            < analysis["minimum_sentence_count"]
        ):
            score -= round(
                weight * 0.3
            )

        return max(
            0,
            score,
        )

    def _score_restrictions(
        self,
        analysis: dict,
        weight: int,
    ) -> int:
        """
        Puntúa cumplimiento de restricciones.
        """

        score = weight

        if analysis["prompt_leakage"]:
            score -= round(
                weight * 0.8
            )

        if analysis["refusal_detected"]:
            score -= round(
                weight * 0.35
            )

        if analysis["generic_text_detected"]:
            score -= round(
                weight * 0.25
            )

        if analysis["sensationalism_detected"]:
            score -= round(
                weight * 0.35
            )

        return max(
            0,
            score,
        )

    def _score_quality(
        self,
        content: str,
        analysis: dict,
        weight: int,
    ) -> int:
        """
        Puntúa legibilidad básica y ausencia de repetición.
        """

        score = weight

        if not content:
            return 0

        if analysis["repetition_ratio"] > 0.35:
            score -= round(
                weight * 0.5
            )

        if analysis["sentences"] < 3:
            score -= round(
                weight * 0.4
            )

        return max(
            0,
            score,
        )

    def _is_truncated(
        self,
        content: str,
        rules: dict,
    ) -> bool:
        """
        Detecta finales incompletos o marcadores de truncamiento.
        Esta versión reconoce correctamente cierres de Markdown
        como *, **, _, __, ` y ~~ para evitar falsos positivos.
        """

        if not content:
            return True

        truncation_rules = rules.get(
            "truncation",
            {},
        )

        stripped = content.rstrip()

        suspicious_endings = self._normalize_list(
            truncation_rules.get(
                "suspicious_endings",
                [],
            ),
            preserve_case=True,
        )

        incomplete_markers = self._normalize_list(
            truncation_rules.get(
                "incomplete_markers",
                [],
            )
        )

        for ending in suspicious_endings:
            if stripped.endswith(ending):
                return True

        normalized_content = self._normalize_text(
            stripped
        )

        for marker in incomplete_markers:
            if self._normalize_text(marker) in normalized_content:
                return True
        # Una elipsis suele indicar texto incompleto.
        if stripped.endswith("..."):
            return True
        # ------------------------------------------
        # Eliminación de cierres Markdown válidos
        # ------------------------------------------
        cleaned = stripped.rstrip()

        while cleaned.endswith(
            (
                "*",
                "_",
                "`",
                "~",
            )
        ):
            cleaned = cleaned[:-1].rstrip()

        if not cleaned:
            return True

        last_character = cleaned[-1]

        valid_endings = {
            ".",
            "!",
            "?",
            ":",
            ";",
            ")",
            "]",
            "}",
            '"',
           "'",
    }

        if last_character in valid_endings:
            return False

        last_line = cleaned.splitlines()[-1].strip()

        # Encabezado Markdown
        if last_line.startswith("#"):
            return False

        # Lista Markdown
        if re.match(r"^[-*]\s+", last_line):
            return False

        # Lista numerada
        if re.match(r"^\d+\.\s+", last_line):
            return False

        return True

    def _extract_headings(
        self,
        content: str,
    ) -> list[str]:
        """
        Extrae encabezados Markdown.
        """

        headings: list[str] = []

        for line in content.splitlines():
            stripped = line.strip()

            if not stripped.startswith("#"):
                continue

            heading = stripped.lstrip("#").strip()

            if heading:
                headings.append(heading)

        return headings

    def _heading_is_present(
        self,
        heading: str,
        normalized_headings: set[str],
    ) -> bool:
        """
        Permite coincidencias exactas o encabezados ampliados.
        """

        normalized_required = self._normalize_text(
            heading
        )

        for current_heading in normalized_headings:
            if (
                current_heading == normalized_required
                or normalized_required in current_heading
            ):
                return True

        return False

    def _contains_markers(
        self,
        content: str,
        markers,
    ) -> bool:
        """
        Busca marcadores normalizados dentro del contenido.
        """

        normalized_content = self._normalize_text(
            content
        )

        for marker in self._normalize_list(markers):
            normalized_marker = self._normalize_text(
                marker
            )

            if (
                normalized_marker
                and normalized_marker
                in normalized_content
            ):
                return True

        return False

    def _calculate_repetition_ratio(
        self,
        content: str,
    ) -> float:
        """
        Calcula repetición aproximada de oraciones.
        """

        sentences = [
            self._normalize_text(sentence)
            for sentence in re.split(
                r"[.!?]+\s*",
                content,
            )
            if sentence.strip()
        ]

        if not sentences:
            return 0.0

        unique_sentences = set(sentences)

        repeated_count = (
            len(sentences)
            - len(unique_sentences)
        )

        return round(
            repeated_count
            / len(sentences),
            3,
        )

    def _count_words(
        self,
        content: str,
    ) -> int:
        """
        Cuenta palabras alfanuméricas.
        """

        return len(
            re.findall(
                r"\b[\wÁÉÍÓÚÜÑáéíóúüñ]+\b",
                content,
                flags=re.UNICODE,
            )
        )

    def _count_sentences(
        self,
        content: str,
    ) -> int:
        """
        Cuenta oraciones terminadas.
        """

        return len(
            re.findall(
                r"[.!?](?:\s|$)",
                content,
            )
        )

    def _load_rules(self) -> dict:
        """
        Carga las reglas oficiales de validación.
        """

        rules = read_yaml(
            VALIDATION_RULES_PATH
        )

        if not isinstance(
            rules,
            dict,
        ):
            raise ValueError(
                "validation_rules.yaml no contiene "
                "una estructura válida."
            )

        return rules

    def _get_stage_rules(
        self,
        rules: dict,
        stage: str,
    ) -> dict:
        """
        Obtiene la configuración específica del Stage.
        """

        stages = rules.get(
            "stages",
            {},
        )

        if not isinstance(
            stages,
            dict,
        ):
            return {}

        stage_rules = stages.get(
            stage,
            {},
        )

        if not isinstance(
            stage_rules,
            dict,
        ):
            return {}

        return stage_rules

    def _get_passing_score(
        self,
        rules: dict,
    ) -> int:
        """
        Devuelve la puntuación mínima oficial.
        """

        general = rules.get(
            "general",
            {},
        )

        return self._safe_int(
            general.get(
                "passing_score",
                self.DEFAULT_PASSING_SCORE,
            ),
            default=self.DEFAULT_PASSING_SCORE,
        )

    def _get_runtime_context(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> RuntimeContext | None:
        """
        Detecta la interfaz del Runtime Framework.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input

        return None

    def _get_project(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> Project:
        """
        Obtiene Project desde cualquiera de las interfaces.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.project

        if isinstance(
            runtime_input,
            Project,
        ):
            return runtime_input

        raise TypeError(
            "ValidatorEngine requiere "
            "Project o RuntimeContext."
        )

    def _get_llm_response(
        self,
        runtime_input: Project | RuntimeContext,
        response: LLMResponse | None,
    ) -> LLMResponse | None:
        """
        Obtiene la respuesta desde RuntimeContext
        o desde el argumento legado.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.llm_response

        return response

    def _normalize_text(
        self,
        value: str,
    ) -> str:
        """
        Convierte texto a una forma comparable sin acentos.
        """

        normalized = unicodedata.normalize(
            "NFKD",
            str(value),
        )

        without_accents = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )

        return (
            without_accents
            .strip()
            .lower()
        )

    def _normalize_list(
        self,
        values,
        preserve_case: bool = False,
    ) -> list[str]:
        """
        Convierte una entrada en lista de textos únicos.
        """

        if not isinstance(
            values,
            list,
        ):
            return []

        normalized_values: list[str] = []

        for value in values:
            text = str(value).strip()

            if not text:
                continue

            final_value = (
                text
                if preserve_case
                else text.upper()
            )

            if final_value not in normalized_values:
                normalized_values.append(
                    final_value
                )

        return normalized_values

    def _safe_ratio(
        self,
        value: int,
        minimum: int,
    ) -> float:
        """
        Evita divisiones por cero.
        """

        if minimum <= 0:
            return 1.0

        return min(
            value / minimum,
            1.0,
        )

    def _safe_int(
        self,
        value,
        default: int,
    ) -> int:
        """
        Convierte un valor a entero.
        """

        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _safe_float(
        self,
        value,
        default: float,
    ) -> float:
        """
        Convierte un valor a flotante.
        """

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _base_metadata(
        self,
        project: Project,
    ) -> dict:
        """
        Construye los metadatos comunes.
        """

        return {
            "component": self.component_name,
            "project_id": project.project_id,
            "stage": project.stage_actual,
        }