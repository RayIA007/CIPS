"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 049
Archivo  : metrics_engine.py
Estado   : RELEASE
=========================================================

Calcula las métricas consolidadas de un proyecto CIPS.

Responsabilidades:
- recibir un FinalProjectObject finalizado;
- contar Stages, archivos, prompts y respuestas;
- calcular caracteres, palabras y líneas;
- recuperar tokens y duración cuando estén disponibles;
- consolidar puntuaciones de validación;
- detectar proveedores, modelos y Knowledge Modules;
- calcular estimaciones básicas de lectura y video;
- construir ProjectMetrics;
- guardar PROJECT_METRICS.json;
- actualizar FinalProjectObject.metrics;
- actualizar el resumen de métricas del manifiesto en memoria.

Este Engine NO:
- modifica contenido editorial;
- llama modelos de Inteligencia Artificial;
- calcula hashes;
- publica contenido;
- genera PDF, DOCX o ZIP.
"""

from dataclasses import asdict
import json
from pathlib import Path
import re
from typing import Any

from runtime_constants import FINAL_STAGE, STAGES
from runtime_models import (
    EngineResult,
    FinalProjectObject,
    ProjectMetrics,
)
from utils import current_datetime, read_yaml


class MetricsEngine:
    """
    Calcula y persiste las métricas técnicas y editoriales
    del proyecto consolidado.

    Entrada:
        FinalProjectObject finalizado.

    Salida:
        PROJECT_METRICS.json
    """

    COMPONENT_NAME = "metrics_engine"
    OUTPUT_FILENAME = "PROJECT_METRICS.json"
    VERSION = "0.7"

    READING_WORDS_PER_MINUTE = 220
    VIDEO_WORDS_PER_MINUTE = 145

    PRODUCTION_STAGES = [
        stage
        for stage in STAGES
        if stage != FINAL_STAGE
    ]

    def execute(
        self,
        final_project: FinalProjectObject,
    ) -> EngineResult:
        """
        Calcula, guarda y registra ProjectMetrics.
        """

        try:
            validation_result = self._validate(
                final_project
            )

            if validation_result is not None:
                return validation_result

            metrics = self._build_metrics(
                final_project
            )

            output_path = self._save_metrics(
                final_project=final_project,
                metrics=metrics,
            )

            final_project.metrics = metrics

            final_project.register_export(
                "metrics",
                output_path,
            )

            if final_project.manifest is not None:
                final_project.manifest.metrics_summary = (
                    self._build_manifest_summary(
                        metrics
                    )
                )

            final_project.metadata[
                "metrics"
            ] = {
                "generated": True,
                "generated_at": current_datetime(),
                "output_path": str(output_path),
                "stages_completed": (
                    metrics.stages_completed
                ),
                "completion_percent": (
                    metrics.completion_percent
                ),
                "total_words": metrics.total_words,
                "total_tokens": metrics.total_tokens,
                "average_validation_score": (
                    metrics.average_validation_score
                ),
            }

            return EngineResult.ok(
                data=final_project,
                message=(
                    "Métricas del proyecto calculadas "
                    "correctamente."
                ),
                warnings=list(
                    final_project.warnings
                ),
                metadata={
                    **self._base_metadata(
                        final_project
                    ),
                    "output_path": str(output_path),
                    "stages_total": metrics.stages_total,
                    "stages_completed": (
                        metrics.stages_completed
                    ),
                    "completion_percent": (
                        metrics.completion_percent
                    ),
                    "files_total": metrics.files_total,
                    "prompts_total": metrics.prompts_total,
                    "responses_total": (
                        metrics.responses_total
                    ),
                    "total_characters": (
                        metrics.total_characters
                    ),
                    "total_words": metrics.total_words,
                    "total_lines": metrics.total_lines,
                    "prompt_tokens": metrics.prompt_tokens,
                    "response_tokens": (
                        metrics.response_tokens
                    ),
                    "thinking_tokens": (
                        metrics.thinking_tokens
                    ),
                    "total_tokens": metrics.total_tokens,
                    "average_validation_score": (
                        metrics.average_validation_score
                    ),
                    "providers_used": (
                        metrics.providers_used
                    ),
                    "models_used": metrics.models_used,
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en MetricsEngine."
                ),
                errors=[str(error)],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

    def _validate(
        self,
        final_project: FinalProjectObject,
    ) -> EngineResult | None:
        """
        Comprueba que el proyecto pueda medirse.
        """

        if final_project is None:
            return EngineResult.fail(
                message=(
                    "No se recibió un FinalProjectObject."
                ),
                errors=[
                    "final_project es None."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        if not isinstance(
            final_project,
            FinalProjectObject,
        ):
            return EngineResult.fail(
                message=(
                    "MetricsEngine requiere un "
                    "FinalProjectObject válido."
                ),
                errors=[
                    "Tipo de entrada incompatible: "
                    f"{type(final_project).__name__}."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        project = final_project.project

        if project is None:
            return EngineResult.fail(
                message=(
                    "FinalProjectObject no contiene Project."
                ),
                errors=[
                    "FinalProjectObject.project es None."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        project_path = Path(
            project.path
        )

        if (
            not project_path.exists()
            or not project_path.is_dir()
        ):
            return EngineResult.fail(
                message=(
                    "La carpeta del proyecto no es válida."
                ),
                errors=[
                    str(project_path)
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        if not final_project.final_content.strip():
            return EngineResult.fail(
                message=(
                    "El proyecto debe finalizarse antes "
                    "de calcular sus métricas."
                ),
                errors=[
                    "FinalProjectObject.final_content vacío."
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        final_path = (
            project_path
            / "07_FINAL.md"
        )

        if not final_path.exists():
            return EngineResult.fail(
                message=(
                    "No existe el documento maestro "
                    "07_FINAL.md."
                ),
                errors=[
                    str(final_path)
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        return None

    def _build_metrics(
        self,
        final_project: FinalProjectObject,
    ) -> ProjectMetrics:
        """
        Construye ProjectMetrics en memoria.
        """

        project_path = Path(
            final_project.project.path
        )

        memory_data = self._read_yaml_dict(
            project_path / "memoria.yaml"
        )

        completed_stages = [
            stage
            for stage in self.PRODUCTION_STAGES
            if final_project.get_stage_content(
                stage
            ).strip()
        ]

        stages_total = len(
            self.PRODUCTION_STAGES
        )

        stages_completed = len(
            completed_stages
        )

        completion_percent = (
            round(
                stages_completed
                / stages_total
                * 100,
                2,
            )
            if stages_total
            else 0.0
        )

        stage_contents = [
            final_project.get_stage_content(
                stage
            )
            for stage in self.PRODUCTION_STAGES
            if final_project.get_stage_content(
                stage
            ).strip()
        ]

        response_text = "\n\n".join(
            stage_contents
        )

        prompt_texts = self._read_registered_files(
            final_project.prompt_files
        )

        prompt_text = "\n\n".join(
            prompt_texts
        )

        total_text = "\n\n".join(
            [
                response_text,
                final_project.final_content,
            ]
        ).strip()

        token_metrics = self._extract_token_metrics(
            memory_data
        )

        validation_scores = (
            self._extract_validation_scores(
                memory_data
            )
        )

        providers, models = (
            self._extract_provider_information(
                memory_data=memory_data,
                final_project=final_project,
            )
        )

        knowledge_modules = (
            self._extract_knowledge_modules(
                memory_data=memory_data,
                final_project=final_project,
            )
        )

        duration_seconds = (
            self._extract_duration_seconds(
                memory_data
            )
        )

        memory_history = memory_data.get(
            "historial",
            [],
        )

        if not isinstance(
            memory_history,
            list,
        ):
            memory_history = []

        files_total = self._count_project_files(
            project_path
        )

        responses_total = len(
            [
                content
                for content in stage_contents
                if content.strip()
            ]
        )

        prompt_characters = len(
            prompt_text
        )

        response_characters = len(
            response_text
        )

        total_words = self._count_words(
            total_text
        )

        total_lines = self._count_lines(
            total_text
        )

        average_score = self._average(
            list(
                validation_scores.values()
            )
        )

        minimum_score = (
            min(validation_scores.values())
            if validation_scores
            else 0.0
        )

        maximum_score = (
            max(validation_scores.values())
            if validation_scores
            else 0.0
        )

        return ProjectMetrics(
            stages_total=stages_total,
            stages_completed=stages_completed,
            completion_percent=completion_percent,
            files_total=files_total,
            prompts_total=len(
                final_project.prompt_files
            ),
            responses_total=responses_total,
            memory_records=len(
                memory_history
            ),
            total_characters=len(
                total_text
            ),
            total_words=total_words,
            total_lines=total_lines,
            prompt_characters=prompt_characters,
            response_characters=response_characters,
            prompt_tokens=token_metrics[
                "prompt_tokens"
            ],
            response_tokens=token_metrics[
                "response_tokens"
            ],
            thinking_tokens=token_metrics[
                "thinking_tokens"
            ],
            total_tokens=token_metrics[
                "total_tokens"
            ],
            duration_seconds=duration_seconds,
            estimated_cost=0.0,
            currency="USD",
            validation_scores=validation_scores,
            average_validation_score=average_score,
            minimum_validation_score=(
                round(
                    float(minimum_score),
                    2,
                )
            ),
            maximum_validation_score=(
                round(
                    float(maximum_score),
                    2,
                )
            ),
            providers_used=providers,
            models_used=models,
            knowledge_modules_used=knowledge_modules,
            metadata={
                "component": self.COMPONENT_NAME,
                "component_version": self.VERSION,
                "generated_at": current_datetime(),
                "completed_stages": completed_stages,
                "reading_words_per_minute": (
                    self.READING_WORDS_PER_MINUTE
                ),
                "video_words_per_minute": (
                    self.VIDEO_WORDS_PER_MINUTE
                ),
                "estimated_reading_minutes": round(
                    total_words
                    / self.READING_WORDS_PER_MINUTE,
                    2,
                ),
                "estimated_video_minutes": round(
                    self._count_words(
                        final_project.script
                    )
                    / self.VIDEO_WORDS_PER_MINUTE,
                    2,
                ),
                "cost_status": (
                    "not_calculated"
                ),
            },
        )

    def _read_registered_files(
        self,
        registered_files: dict[str, str],
    ) -> list[str]:
        """
        Lee archivos registrados que existan.
        """

        contents: list[str] = []

        for file_path_string in (
            registered_files.values()
        ):
            file_path = Path(
                file_path_string
            )

            if (
                not file_path.exists()
                or not file_path.is_file()
            ):
                continue

            content = file_path.read_text(
                encoding="utf-8"
            ).strip()

            if content:
                contents.append(
                    content
                )

        return contents

    def _extract_token_metrics(
        self,
        memory_data: dict[str, Any],
    ) -> dict[str, int]:
        """
        Suma tokens almacenados en el historial.
        """

        totals = {
            "prompt_tokens": 0,
            "response_tokens": 0,
            "thinking_tokens": 0,
            "total_tokens": 0,
        }

        history = memory_data.get(
            "historial",
            [],
        )

        if not isinstance(
            history,
            list,
        ):
            return totals

        for record in history:
            if not isinstance(
                record,
                dict,
            ):
                continue

            metadata = record.get(
                "metadata",
                {},
            )

            if not isinstance(
                metadata,
                dict,
            ):
                continue

            for field_name in totals:
                value = metadata.get(
                    field_name,
                    0,
                )

                totals[field_name] += (
                    self._safe_int(
                        value
                    )
                )

        if (
            totals["total_tokens"] == 0
            and (
                totals["prompt_tokens"]
                or totals["response_tokens"]
                or totals["thinking_tokens"]
            )
        ):
            totals["total_tokens"] = (
                totals["prompt_tokens"]
                + totals["response_tokens"]
                + totals["thinking_tokens"]
            )

        return totals

    def _extract_validation_scores(
        self,
        memory_data: dict[str, Any],
    ) -> dict[str, float]:
        """
        Extrae puntuaciones de validación por Stage.
        """

        scores: dict[str, float] = {}

        history = memory_data.get(
            "historial",
            [],
        )

        if not isinstance(
            history,
            list,
        ):
            return scores

        for record in history:
            if not isinstance(
                record,
                dict,
            ):
                continue

            stage = str(
                record.get(
                    "stage",
                    "",
                )
            ).strip()

            metadata = record.get(
                "metadata",
                {},
            )

            if (
                not stage
                or not isinstance(
                    metadata,
                    dict,
                )
            ):
                continue

            score = metadata.get(
                "score",
                metadata.get(
                    "validation_score"
                ),
            )

            numeric_score = self._safe_float(
                score,
                default=None,
            )

            if numeric_score is not None:
                scores[stage] = round(
                    numeric_score,
                    2,
                )

        return scores

    def _extract_provider_information(
        self,
        memory_data: dict[str, Any],
        final_project: FinalProjectObject,
    ) -> tuple[list[str], list[str]]:
        """
        Obtiene proveedores y modelos registrados.
        """

        providers: list[str] = []
        models: list[str] = []

        if final_project.manifest is not None:
            for provider in (
                final_project.manifest.providers
            ):
                self._append_unique(
                    providers,
                    provider,
                )

            for model in (
                final_project.manifest.models
            ):
                self._append_unique(
                    models,
                    model,
                )

        history = memory_data.get(
            "historial",
            [],
        )

        if isinstance(
            history,
            list,
        ):
            for record in history:
                if not isinstance(
                    record,
                    dict,
                ):
                    continue

                metadata = record.get(
                    "metadata",
                    {},
                )

                if not isinstance(
                    metadata,
                    dict,
                ):
                    continue

                self._append_unique(
                    providers,
                    metadata.get(
                        "provider"
                    ),
                )

                self._append_unique(
                    models,
                    metadata.get(
                        "model"
                    ),
                )

        return providers, models

    def _extract_knowledge_modules(
        self,
        memory_data: dict[str, Any],
        final_project: FinalProjectObject,
    ) -> list[str]:
        """
        Extrae IDs de Knowledge Modules cuando existen.
        """

        module_ids: list[str] = []

        history = memory_data.get(
            "historial",
            [],
        )

        if isinstance(
            history,
            list,
        ):
            for record in history:
                if not isinstance(
                    record,
                    dict,
                ):
                    continue

                metadata = record.get(
                    "metadata",
                    {},
                )

                if not isinstance(
                    metadata,
                    dict,
                ):
                    continue

                candidates = (
                    metadata.get(
                        "knowledge_modules"
                    )
                    or metadata.get(
                        "selected_ids"
                    )
                    or metadata.get(
                        "modules"
                    )
                    or []
                )

                if not isinstance(
                    candidates,
                    list,
                ):
                    continue

                for candidate in candidates:
                    self._append_unique(
                        module_ids,
                        candidate,
                    )

        metadata_candidates = (
            final_project.metadata.get(
                "knowledge_modules",
                [],
            )
        )

        if isinstance(
            metadata_candidates,
            list,
        ):
            for candidate in metadata_candidates:
                self._append_unique(
                    module_ids,
                    candidate,
                )

        return module_ids

    def _extract_duration_seconds(
        self,
        memory_data: dict[str, Any],
    ) -> float:
        """
        Suma duración registrada por Stage.
        """

        total = 0.0

        history = memory_data.get(
            "historial",
            [],
        )

        if not isinstance(
            history,
            list,
        ):
            return total

        for record in history:
            if not isinstance(
                record,
                dict,
            ):
                continue

            metadata = record.get(
                "metadata",
                {},
            )

            if not isinstance(
                metadata,
                dict,
            ):
                continue

            duration = metadata.get(
                "duration_seconds",
                0,
            )

            total += (
                self._safe_float(
                    duration,
                    default=0.0,
                )
                or 0.0
            )

        return round(
            total,
            2,
        )

    def _count_project_files(
        self,
        project_path: Path,
    ) -> int:
        """
        Cuenta archivos reales del proyecto.
        """

        return sum(
            1
            for file_path in project_path.rglob("*")
            if file_path.is_file()
            and "__pycache__"
            not in file_path.parts
            and file_path.suffix.lower()
            not in {
                ".tmp",
                ".pyc",
            }
        )

    def _count_words(
        self,
        content: str,
    ) -> int:
        """
        Cuenta palabras Unicode.
        """

        return len(
            re.findall(
                r"\b[\wÁÉÍÓÚÜÑáéíóúüñ]+\b",
                content,
                flags=re.UNICODE,
            )
        )

    def _count_lines(
        self,
        content: str,
    ) -> int:
        """
        Cuenta líneas del contenido.
        """

        if not content:
            return 0

        return len(
            content.splitlines()
        )

    def _average(
        self,
        values: list[float],
    ) -> float:
        """
        Calcula un promedio seguro.
        """

        if not values:
            return 0.0

        return round(
            sum(values)
            / len(values),
            2,
        )

    def _build_manifest_summary(
        self,
        metrics: ProjectMetrics,
    ) -> dict[str, Any]:
        """
        Construye un resumen compacto para ProjectManifest.
        """

        return {
            "stages_total": metrics.stages_total,
            "stages_completed": (
                metrics.stages_completed
            ),
            "completion_percent": (
                metrics.completion_percent
            ),
            "files_total": metrics.files_total,
            "total_characters": (
                metrics.total_characters
            ),
            "total_words": metrics.total_words,
            "total_tokens": metrics.total_tokens,
            "duration_seconds": (
                metrics.duration_seconds
            ),
            "average_validation_score": (
                metrics.average_validation_score
            ),
            "providers_used": (
                metrics.providers_used
            ),
            "models_used": metrics.models_used,
        }

    def _save_metrics(
        self,
        final_project: FinalProjectObject,
        metrics: ProjectMetrics,
    ) -> Path:
        """
        Guarda PROJECT_METRICS.json de forma atómica.
        """

        output_path = (
            final_project.project.path
            / self.OUTPUT_FILENAME
        )

        temporary_path = output_path.with_suffix(
            f"{output_path.suffix}.tmp"
        )

        json_content = json.dumps(
            asdict(metrics),
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )

        temporary_path.write_text(
            json_content + "\n",
            encoding="utf-8",
        )

        temporary_path.replace(
            output_path
        )

        return output_path

    def _read_yaml_dict(
        self,
        file_path: Path,
    ) -> dict[str, Any]:
        """
        Lee YAML y garantiza un diccionario.
        """

        if not file_path.exists():
            return {}

        data = read_yaml(
            file_path
        )

        if not isinstance(
            data,
            dict,
        ):
            return {}

        return data

    def _append_unique(
        self,
        values: list[str],
        value: Any,
    ) -> None:
        """
        Agrega texto no vacío sin duplicados.
        """

        if value is None:
            return

        normalized = str(
            value
        ).strip()

        if (
            normalized
            and normalized not in values
        ):
            values.append(
                normalized
            )

    def _safe_int(
        self,
        value: Any,
    ) -> int:
        """
        Convierte a entero seguro.
        """

        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _safe_float(
        self,
        value: Any,
        default: float | None = 0.0,
    ) -> float | None:
        """
        Convierte a flotante seguro.
        """

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _base_metadata(
        self,
        final_project: FinalProjectObject,
    ) -> dict[str, Any]:
        """
        Construye metadatos comunes.
        """

        project = final_project.project

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "project_id": project.project_id,
            "project_path": str(project.path),
            "project_stage": project.stage_actual,
            "output_filename": self.OUTPUT_FILENAME,
        }

    def get_component_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve información pública del componente.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "output_file": self.OUTPUT_FILENAME,
            "writes_files": True,
            "requires_finalized_project": True,
            "updates_manifest_in_memory": True,
            "cost_calculation": False,
            "next_engine": "export_engine",
        }