"""Production routing for legacy sequential multimedia stages in CIPS.

Acceptance Fix 02 closes the historical gap where ``PipelineEngine`` sent
multimedia stages through the generic LLM/text persistence path.  This module
keeps media generation behind F4 provider adapters, validates the physical
media before accepting it, and registers the resulting bytes through the F5/F3
artifact persistence boundary.

It deliberately does not call external SDKs directly.  The concrete local
backends in ``11_MEDIA_PRODUCTION`` are loaded lazily and injected into the F4
callable adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import shutil
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4

from capability_resolver import CapabilityResolver
from cips_core.adapters.contracts import AdapterContext, AdapterRequest
from cips_core.adapters.media import (
    ImageMediaAdapter,
    VideoMediaAdapter,
    VoiceMediaAdapter,
)
from media_director import CapabilityProviderExecutor, MediaArtifactPersister
from media_director.models import MediaResult as DirectorMediaResult, MediaType
from media_provider import MediaRequest
from media_provider_adapters import (
    ImageGenerationAdapter,
    VideoRenderingAdapter,
    VoiceSynthesisAdapter,
)
from media_provider_registry import MediaProviderRegistry
from workspace_resolver import WorkspaceResolver


Backend = Callable[..., Any]

MEDIA_STAGE_CAPABILITIES: dict[str, str] = {
    "voz": "voice_synthesis",
    "imagenes": "image_generation",
    "subtitulos": "subtitle_generation",
    "ensamblado": "video_rendering",
}

_PROVIDER_NAMES: dict[str, str] = {
    "voz": "local_edge_tts",
    "imagenes": "local_pillow",
    "subtitulos": "local_subtitle_timing",
    "ensamblado": "local_moviepy",
}

_BACKEND_SPECS: dict[str, tuple[str, str]] = {
    "voz": ("voice/voice_generator.py", "generar_voz_desde_guion"),
    "imagenes": ("images/image_generator.py", "generar_imagenes_storyboard"),
    "subtitulos": ("subtitles/subtitle_generator.py", "generar_subtitulos_desde_narracion"),
    "ensamblado": ("assembly/video_assembler.py", "ensamblar_video_vertical"),
}


@dataclass(slots=True)
class ProductionMediaResult:
    stage: str
    success: bool
    message: str
    response_path: str = ""
    artifact_paths: list[str] = field(default_factory=list)
    artifact_records: list[dict[str, Any]] = field(default_factory=list)
    provider: str = ""
    capability: str = ""
    reused_existing: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ProductionMediaRouter:
    """Routes production media plus deterministic timed-text stages locally."""

    handled_stages = frozenset(MEDIA_STAGE_CAPABILITIES)

    def __init__(
        self,
        *,
        workspace_resolver: WorkspaceResolver | None = None,
        backend_overrides: Mapping[str, Backend] | None = None,
    ) -> None:
        self.workspace_resolver = workspace_resolver or WorkspaceResolver()
        self.artifact_persister = MediaArtifactPersister(self.workspace_resolver)
        self._backend_overrides = dict(backend_overrides or {})
        self._loaded_backends: dict[str, Backend] = {}

    def handles(self, stage: str) -> bool:
        return str(stage).strip().lower() in self.handled_stages

    def execute(self, project: Any, stage: str) -> ProductionMediaResult:
        normalized_stage = str(stage).strip().lower()
        if normalized_stage not in self.handled_stages:
            return ProductionMediaResult(
                stage=normalized_stage,
                success=False,
                message=f"Stage multimedia no soportado: {normalized_stage}",
                errors=[f"unsupported_media_stage:{normalized_stage}"],
            )

        try:
            if normalized_stage == "voz":
                return self._execute_voice(project)
            if normalized_stage == "imagenes":
                return self._execute_images(project)
            if normalized_stage == "subtitulos":
                return self._execute_subtitles(project)
            return self._execute_video(project)
        except Exception as error:
            return ProductionMediaResult(
                stage=normalized_stage,
                success=False,
                message=f"Falló el routing multimedia del Stage '{normalized_stage}'.",
                errors=[f"{type(error).__name__}: {error}"],
                capability=MEDIA_STAGE_CAPABILITIES[normalized_stage],
                provider=_PROVIDER_NAMES[normalized_stage],
                metadata={"exception_type": type(error).__name__},
            )

    def validate_quality_gate(self, project: Any) -> ProductionMediaResult:
        """Validates every physical media prerequisite before quality control."""

        project_path = Path(project.path)
        audio_path = project_path / "voice" / "audio.mp3"
        image_paths = self._image_paths(project_path)
        raw_video = project_path / "video" / "raw_video.mp4"
        final_video = project_path / "final" / "short.mp4"
        subtitles = project_path / "subtitles" / "subtitles.srt"

        errors: list[str] = []
        errors.extend(self._validation_errors(audio_path, "audio"))
        if not image_paths:
            errors.append("No existen imágenes físicas en images/.")
        else:
            for path in image_paths:
                errors.extend(self._validation_errors(path, "image"))
        errors.extend(self._validation_errors(raw_video, "video"))
        errors.extend(self._validation_errors(final_video, "video"))

        subtitle_errors = self._subtitle_validation_errors(subtitles)
        errors.extend(subtitle_errors)

        artifact_paths = [audio_path, *image_paths, raw_video, final_video]
        for path in artifact_paths:
            if path.is_file():
                sidecar = Path(f"{path}.meta.json")
                if not sidecar.is_file():
                    errors.append(f"Falta sidecar F3 para {path.name}.")
                    continue
                sidecar_error = self._sidecar_integrity_error(path, sidecar)
                if sidecar_error:
                    errors.append(sidecar_error)

        return ProductionMediaResult(
            stage="control_calidad",
            success=not errors,
            message=(
                "Preflight multimedia de control de calidad aprobado."
                if not errors
                else "Control de calidad bloqueado por artifacts multimedia inválidos."
            ),
            response_path=str(final_video),
            artifact_paths=[str(path) for path in artifact_paths if path.is_file()],
            provider="local_media_validation",
            capability="media_quality_gate",
            errors=errors,
            metadata={
                "validation_approved": not errors,
                "validation_score": 100 if not errors else 0,
                "validation_passing_score": 100,
                "media_quality_gate": True,
            },
        )

    def _execute_voice(self, project: Any) -> ProductionMediaResult:
        project_path = Path(project.path)
        audio_path = project_path / "voice" / "audio.mp3"
        reused = self._is_valid_media(audio_path, "audio")

        if not reused:
            self._remove_invalid_file(audio_path, "audio")
            stack_result = self._invoke_media_stack("voz", project)
            audio_path = self._single_output_path(self._stack_output(stack_result), project_path)

        errors = self._validation_errors(audio_path, "audio")
        if errors:
            return self._invalid_media_result("voz", audio_path, errors)

        artifact_record = self._persist_binary_artifact(
            project=project,
            stage="voz",
            path=audio_path,
            media_type=MediaType.VOICE,
            mime_type="audio/mpeg",
        )
        return self._success_result(
            stage="voz",
            response_path=audio_path,
            artifact_paths=[audio_path],
            artifact_records=[artifact_record],
            reused=reused,
        )

    def _execute_images(self, project: Any) -> ProductionMediaResult:
        project_path = Path(project.path)
        self._prepare_images_directory(project_path)
        existing = self._image_paths(project_path)
        reused = bool(existing) and all(
            self._is_valid_media(path, "image") for path in existing
        )

        if reused:
            image_paths = existing
        else:
            for path in existing:
                if not self._is_valid_media(path, "image"):
                    path.unlink(missing_ok=True)
            stack_result = self._invoke_media_stack("imagenes", project)
            image_paths = self._many_output_paths(self._stack_output(stack_result), project_path)

        if not image_paths:
            return self._invalid_media_result(
                "imagenes",
                project_path / "images",
                ["El backend de imágenes no produjo archivos."],
            )

        errors: list[str] = []
        for path in image_paths:
            errors.extend(self._validation_errors(path, "image"))
        if errors:
            return self._invalid_media_result("imagenes", project_path / "images", errors)

        records = [
            self._persist_binary_artifact(
                project=project,
                stage="imagenes",
                path=path,
                media_type=MediaType.IMAGE,
                mime_type=self._image_mime(path),
            )
            for path in image_paths
        ]
        return self._success_result(
            stage="imagenes",
            response_path=project_path / "images",
            artifact_paths=image_paths,
            artifact_records=records,
            reused=reused,
        )

    def _execute_subtitles(self, project: Any) -> ProductionMediaResult:
        project_path = Path(project.path)
        subtitles_path = project_path / "subtitles" / "subtitles.srt"
        reused = not self._subtitle_validation_errors(subtitles_path)

        if not reused:
            self._preserve_invalid_subtitles(subtitles_path)
            backend = self._backend_for("subtitulos")
            output = backend(project_path)
            subtitles_path = self._single_output_path(output, project_path)

        errors = self._subtitle_validation_errors(subtitles_path)
        if errors:
            return ProductionMediaResult(
                stage="subtitulos",
                success=False,
                message="El Stage 'subtitulos' produjo un SRT inválido.",
                response_path=str(subtitles_path),
                errors=errors,
                provider=_PROVIDER_NAMES["subtitulos"],
                capability=MEDIA_STAGE_CAPABILITIES["subtitulos"],
                metadata={
                    "validation_approved": False,
                    "validation_score": 0,
                    "validation_passing_score": 100,
                    "validation_mode": "timed_text",
                },
            )

        return ProductionMediaResult(
            stage="subtitulos",
            success=True,
            message="Stage determinista 'subtitulos' producido y validado correctamente.",
            response_path=str(subtitles_path),
            artifact_paths=[str(subtitles_path)],
            provider=_PROVIDER_NAMES["subtitulos"],
            capability=MEDIA_STAGE_CAPABILITIES["subtitulos"],
            reused_existing=reused,
            metadata={
                "validation_approved": True,
                "validation_score": 100,
                "validation_passing_score": 100,
                "validation_mode": "timed_text",
                "binary_validation": False,
                "artifact_count": 1,
                "size_bytes": subtitles_path.stat().st_size,
                "deterministic_stage": True,
            },
        )

    def _execute_video(self, project: Any) -> ProductionMediaResult:
        project_path = Path(project.path)
        prerequisite_errors: list[str] = []
        prerequisite_errors.extend(
            self._validation_errors(project_path / "voice" / "audio.mp3", "audio")
        )
        image_paths = self._image_paths(project_path)
        if not image_paths:
            prerequisite_errors.append("No existen imágenes válidas para ensamblado.")
        else:
            for path in image_paths:
                prerequisite_errors.extend(self._validation_errors(path, "image"))
        if prerequisite_errors:
            return ProductionMediaResult(
                stage="ensamblado",
                success=False,
                message="Ensamblado bloqueado por inputs multimedia inválidos.",
                errors=prerequisite_errors,
                provider=_PROVIDER_NAMES["ensamblado"],
                capability=MEDIA_STAGE_CAPABILITIES["ensamblado"],
            )

        final_video = project_path / "final" / "short.mp4"
        raw_video = project_path / "video" / "raw_video.mp4"
        reused = self._is_valid_media(final_video, "video") or self._is_valid_media(
            raw_video, "video"
        )

        if reused:
            source = final_video if self._is_valid_media(final_video, "video") else raw_video
        else:
            self._remove_invalid_file(final_video, "video")
            self._remove_invalid_file(raw_video, "video")
            stack_result = self._invoke_media_stack("ensamblado", project)
            source = self._single_output_path(self._stack_output(stack_result), project_path)

        source_errors = self._validation_errors(source, "video")
        if source_errors:
            return self._invalid_media_result("ensamblado", source, source_errors)

        raw_video.parent.mkdir(parents=True, exist_ok=True)
        final_video.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve(strict=False) != raw_video.resolve(strict=False):
            shutil.copy2(source, raw_video)
        if source.resolve(strict=False) != final_video.resolve(strict=False):
            shutil.copy2(source, final_video)

        errors = [
            *self._validation_errors(raw_video, "video"),
            *self._validation_errors(final_video, "video"),
        ]
        if errors:
            return self._invalid_media_result("ensamblado", raw_video, errors)

        raw_record = self._persist_binary_artifact(
            project=project,
            stage="ensamblado",
            path=raw_video,
            media_type=MediaType.VIDEO,
            mime_type="video/mp4",
            artifact_role="raw_video",
        )
        final_record = self._persist_binary_artifact(
            project=project,
            stage="ensamblado",
            path=final_video,
            media_type=MediaType.VIDEO,
            mime_type="video/mp4",
            artifact_role="final_video",
        )
        return self._success_result(
            stage="ensamblado",
            response_path=raw_video,
            artifact_paths=[raw_video, final_video],
            artifact_records=[raw_record, final_record],
            reused=reused,
        )

    def _invoke_media_stack(self, stage: str, project: Any):
        """Recorre Core Adapter -> MediaDirector -> F5 executor -> F4 provider."""

        project_path = Path(project.path)
        backend = self._backend_for(stage)
        provider_name = _PROVIDER_NAMES[stage]
        if stage == "voz":
            provider = VoiceSynthesisAdapter(backend, provider_name=provider_name)
            adapter_class = VoiceMediaAdapter
        elif stage == "imagenes":
            provider = ImageGenerationAdapter(backend, provider_name=provider_name)
            adapter_class = ImageMediaAdapter
        else:
            provider = VideoRenderingAdapter(backend, provider_name=provider_name)
            adapter_class = VideoMediaAdapter

        resolver = CapabilityResolver(MediaProviderRegistry([provider]))

        def provider_invoker(selected_provider: Any, work_package: Any) -> Any:
            provider_result = selected_provider.generate(
                MediaRequest(
                    capability=work_package.capability,
                    payload=project_path,
                    metadata=dict(work_package.metadata),
                )
            )
            if not provider_result.success:
                details = "; ".join(str(item) for item in provider_result.errors)
                raise RuntimeError(
                    provider_result.message
                    + (f": {details}" if details else "")
                )
            return provider_result.output

        provider_executor = CapabilityProviderExecutor(
            resolver,
            provider_invoker=provider_invoker,
        )
        media_adapter = adapter_class(provider_executor=provider_executor)
        adapter_request = AdapterRequest(
            capability=MEDIA_STAGE_CAPABILITIES[stage],
            context=AdapterContext(
                project_id=project.project_id,
                workflow_id="legacy_full_pipeline",
                run_id=f"{project.project_id}_production",
                task_id=stage,
                correlation_id=f"production_{stage}_{uuid4().hex[:16]}",
                metadata={
                    "production_acceptance_fix": "02",
                    "legacy_stage": stage,
                },
            ),
            input_data={
                "prompt": self._stage_prompt(project_path, stage),
                "metadata": {
                    "project_path": str(project_path),
                    "provider": provider_name,
                },
            },
        )
        return media_adapter.execute(adapter_request)

    @staticmethod
    def _stage_prompt(project_path: Path, stage: str) -> str:
        candidates = {
            "voz": (
                project_path / "narration" / "narration.txt",
                project_path / "script" / "03_GUION.md",
            ),
            "imagenes": (project_path / "storyboard" / "04_STORYBOARD.md",),
            "ensamblado": (
                project_path / "subtitles" / "subtitles.srt",
                project_path / "narration" / "narration.txt",
            ),
        }[stage]
        for path in candidates:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                continue
            if text:
                return text
        return f"Producción multimedia CIPS para Stage {stage}."

    @staticmethod
    def _stack_output(adapter_result: Any) -> Any:
        if not getattr(adapter_result, "succeeded", False):
            raise RuntimeError(
                getattr(adapter_result, "error", "Media Adapter no aprobado.")
            )
        output = getattr(adapter_result, "output", None)
        if not isinstance(output, Mapping) or "output" not in output:
            raise TypeError("Media Adapter no devolvió MediaResult serializado.")
        return output["output"]

    def _backend_for(self, stage: str) -> Backend:
        override = self._backend_overrides.get(stage)
        if override is not None:
            if not callable(override):
                raise TypeError(f"backend_overrides['{stage}'] debe ser callable.")
            return override
        if stage in self._loaded_backends:
            return self._loaded_backends[stage]

        relative_module, function_name = _BACKEND_SPECS[stage]
        module_path = Path(__file__).resolve().parent.parent / "11_MEDIA_PRODUCTION" / relative_module
        if not module_path.is_file():
            raise FileNotFoundError(f"Backend multimedia no encontrado: {module_path}")

        module_name = f"cips_production_media_{stage}_{uuid4().hex}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"No fue posible cargar el backend: {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        backend = getattr(module, function_name, None)
        if not callable(backend):
            raise AttributeError(f"Backend '{function_name}' no disponible en {module_path}")
        self._loaded_backends[stage] = backend
        return backend

    def _persist_binary_artifact(
        self,
        *,
        project: Any,
        stage: str,
        path: Path,
        media_type: MediaType,
        mime_type: str,
        artifact_role: str | None = None,
    ) -> dict[str, Any]:
        content = path.read_bytes()
        relative_path = path.resolve(strict=False).relative_to(
            Path(project.path).resolve(strict=False)
        )
        result = DirectorMediaResult(
            request_id=f"production_{stage}_{uuid4().hex[:16]}",
            strategy_name=f"production_{stage}",
            media_type=media_type,
            capability=MEDIA_STAGE_CAPABILITIES[stage],
            output_format=path.suffix.lstrip(".").lower() or media_type.value,
            output=content,
            metadata={
                "provider": _PROVIDER_NAMES[stage],
                "project_id": project.project_id,
                "stage": stage,
                "source_path": str(path),
                "artifact_role": artifact_role or stage,
            },
        )
        written = self.artifact_persister.persist(
            result,
            workspace_root=project.path,
            relative_path=relative_path,
            mime_type=mime_type,
            metadata={
                "production_acceptance_fix": "02",
                "artifact_role": artifact_role or stage,
            },
        )
        artifact = written.artifact
        return {
            "artifact_type": artifact.artifact_type,
            "artifact_id": artifact.artifact_id,
            "path": artifact.path,
            "mime_type": artifact.mime_type,
            "content_hash": artifact.content_hash,
            "size_bytes": artifact.size_bytes,
            "created_at": written.created_at,
            "sidecar_path": str(written.sidecar_path),
            "deduplicated": written.deduplicated,
            "event_created": written.event_created,
        }

    def _success_result(
        self,
        *,
        stage: str,
        response_path: Path,
        artifact_paths: Iterable[Path],
        artifact_records: list[dict[str, Any]],
        reused: bool,
    ) -> ProductionMediaResult:
        paths = [Path(path) for path in artifact_paths]
        return ProductionMediaResult(
            stage=stage,
            success=True,
            message=f"Stage multimedia '{stage}' producido y validado correctamente.",
            response_path=str(response_path),
            artifact_paths=[str(path) for path in paths],
            artifact_records=artifact_records,
            provider=_PROVIDER_NAMES[stage],
            capability=MEDIA_STAGE_CAPABILITIES[stage],
            reused_existing=reused,
            metadata={
                "validation_approved": True,
                "validation_score": 100,
                "validation_passing_score": 100,
                "media_routing": "production",
                "binary_validation": True,
                "artifact_count": len(paths),
                "size_bytes": sum(path.stat().st_size for path in paths if path.is_file()),
            },
        )

    def _invalid_media_result(
        self,
        stage: str,
        response_path: Path,
        errors: list[str],
    ) -> ProductionMediaResult:
        return ProductionMediaResult(
            stage=stage,
            success=False,
            message=f"El Stage multimedia '{stage}' produjo artifacts inválidos.",
            response_path=str(response_path),
            errors=errors,
            provider=_PROVIDER_NAMES[stage],
            capability=MEDIA_STAGE_CAPABILITIES[stage],
            metadata={
                "validation_approved": False,
                "validation_score": 0,
                "validation_passing_score": 100,
                "binary_validation": False,
            },
        )

    @staticmethod
    def _single_output_path(output: Any, project_path: Path) -> Path:
        if not isinstance(output, (str, Path)):
            raise TypeError("El backend multimedia debe devolver una ruta de archivo.")
        path = Path(output).resolve(strict=False)
        ProductionMediaRouter._assert_within_project(path, project_path)
        return path

    @staticmethod
    def _many_output_paths(output: Any, project_path: Path) -> list[Path]:
        if isinstance(output, (str, Path)):
            values = [output]
        elif isinstance(output, Iterable) and not isinstance(output, (bytes, bytearray, memoryview)):
            values = list(output)
        else:
            raise TypeError("El backend de imágenes debe devolver una colección de rutas.")
        paths = [Path(value).resolve(strict=False) for value in values]
        for path in paths:
            ProductionMediaRouter._assert_within_project(path, project_path)
        return sorted(paths)

    @staticmethod
    def _assert_within_project(path: Path, project_path: Path) -> None:
        try:
            path.relative_to(project_path.resolve(strict=False))
        except ValueError as error:
            raise ValueError(f"El backend devolvió una ruta fuera del proyecto: {path}") from error

    @staticmethod
    def _prepare_images_directory(project_path: Path) -> None:
        """Recovers legacy runs where ``images`` was persisted as text."""

        images_path = project_path / "images"
        if images_path.is_file():
            legacy_path = project_path / "images.invalid_legacy_response.txt"
            if legacy_path.exists():
                legacy_path = project_path / (
                    f"images.invalid_legacy_response.{uuid4().hex[:8]}.txt"
                )
            images_path.replace(legacy_path)
        images_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _image_paths(project_path: Path) -> list[Path]:
        images_dir = project_path / "images"
        if not images_dir.is_dir():
            return []
        suffixes = {".png", ".jpg", ".jpeg", ".webp"}
        return sorted(
            path for path in images_dir.iterdir()
            if path.is_file() and path.suffix.lower() in suffixes
        )

    @staticmethod
    def _remove_invalid_file(path: Path, media_kind: str) -> None:
        if path.is_file() and not ProductionMediaRouter._is_valid_media(path, media_kind):
            path.unlink(missing_ok=True)

    @staticmethod
    def _validation_errors(path: Path, media_kind: str) -> list[str]:
        if not path.is_file():
            return [f"Artifact {media_kind} no encontrado: {path}"]
        if path.stat().st_size <= 0:
            return [f"Artifact {media_kind} vacío: {path}"]
        if not ProductionMediaRouter._is_valid_media(path, media_kind):
            return [f"Artifact {media_kind} no tiene una firma binaria válida: {path}"]
        return []

    @staticmethod
    def _is_valid_media(path: Path, media_kind: str) -> bool:
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        head = path.read_bytes()[:64]
        if media_kind == "audio":
            return head.startswith(b"ID3") or (
                len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0
            )
        if media_kind == "video":
            return len(head) >= 12 and b"ftyp" in head[4:32]
        if media_kind == "image":
            suffix = path.suffix.lower()
            if suffix == ".png":
                return head.startswith(b"\x89PNG\r\n\x1a\n")
            if suffix in {".jpg", ".jpeg"}:
                return head.startswith(b"\xff\xd8\xff")
            if suffix == ".webp":
                return len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"WEBP"
        return False

    @staticmethod
    def _image_mime(path: Path) -> str:
        suffix = path.suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }[suffix]

    @staticmethod
    def _subtitle_validation_errors(path: Path) -> list[str]:
        if not path.is_file() or path.stat().st_size <= 0:
            return [f"No existe un archivo de subtítulos válido: {path}"]
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [f"subtitles.srt no es UTF-8 válido: {error}"]

        cue_pattern = re.compile(
            r"(?m)^\s*\d+\s*\n"
            r"\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+"
            r"\d{2}:\d{2}:\d{2},\d{3}\s*$"
        )
        if not cue_pattern.search(text):
            return ["subtitles.srt no contiene bloques SRT con marcas temporales válidas."]
        return []

    @staticmethod
    def _preserve_invalid_subtitles(path: Path) -> None:
        if not path.is_file():
            return
        target = path.with_name("subtitles.invalid_legacy_response.txt")
        if target.exists():
            target = path.with_name(
                f"subtitles.invalid_legacy_response.{uuid4().hex[:8]}.txt"
            )
        path.replace(target)

    @staticmethod
    def _sidecar_integrity_error(path: Path, sidecar: Path) -> str:
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            return f"Sidecar inválido para {path.name}: {error}"
        expected_hash = str(data.get("content_hash", "")).strip().lower()
        if not expected_hash:
            return f"Sidecar sin content_hash para {path.name}."
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            return f"Hash F3 no coincide para {path.name}."
        return ""


__all__ = [
    "MEDIA_STAGE_CAPABILITIES",
    "ProductionMediaResult",
    "ProductionMediaRouter",
]
