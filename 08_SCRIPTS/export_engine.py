"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 050
Archivo  : export_engine.py
Estado   : RELEASE
=========================================================

Orquesta las exportaciones de un proyecto CIPS finalizado.

Responsabilidades:
- recibir un FinalProjectObject completo;
- validar que existan finalización, manifiesto y métricas;
- resolver los formatos solicitados;
- ejecutar los Exporters registrados;
- detenerse ante errores críticos;
- consolidar rutas y resultados de exportación;
- actualizar FinalProjectObject.exports;
- preparar el paquete para ZIPExporter y publicación futura.

Este Engine NO:
- construye contenido editorial;
- llama modelos de Inteligencia Artificial;
- calcula métricas;
- calcula hashes del manifiesto;
- implementa directamente formatos de archivo;
- publica contenido en plataformas externas.

Los formatos concretos pertenecen a Exporters independientes:

- MarkdownExporter
- JSONExporter
- ZIPExporter
- futuros DOCXExporter y PDFExporter
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from runtime_models import (
    EngineResult,
    FinalProjectObject,
)


@dataclass
class ExportExecution:
    """
    Registra el resultado de un Exporter individual.
    """

    export_format: str
    success: bool
    message: str = ""
    output_path: str = ""
    warnings: list[str] = field(
        default_factory=list
    )
    errors: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class ExportEngine:
    """
    Coordinador central de exportaciones.

    Entrada:
        FinalProjectObject finalizado, medido y manifestado.

    Salida:
        FinalProjectObject con rutas de exportación registradas.

    Ejemplo futuro:

        ExportEngine().execute(
            final_project,
            formats=["markdown", "json", "zip"],
        )
    """

    COMPONENT_NAME = "export_engine"
    VERSION = "0.7"

    DEFAULT_EXPORT_DIRECTORY = "06_EXPORTACIONES"

    DEFAULT_FORMATS = [
        "markdown",
        "json",
    ]

    SUPPORTED_FORMATS = {
        "markdown",
        "json",
        "zip",
    }

    FORMAT_ALIASES = {
        "md": "markdown",
        "markdown": "markdown",
        "json": "json",
        "zip": "zip",
    }

    def __init__(
        self,
        exporters: dict[str, Any] | None = None,
    ) -> None:
        """
        Inicializa el coordinador.

        Args:
            exporters:
                Registro opcional de Exporters ya construidos.

                Ejemplo:

                {
                    "markdown": MarkdownExporter(),
                    "json": JSONExporter(),
                }

        Si no se proporciona, los Exporters se cargarán
        de forma diferida al ejecutar cada formato.
        """

        self._exporters: dict[str, Any] = {}

        if exporters:
            for export_format, exporter in exporters.items():
                self.register_exporter(
                    export_format=export_format,
                    exporter=exporter,
                )

    # --------------------------------------------------
    # API pública
    # --------------------------------------------------

    def execute(
        self,
        final_project: FinalProjectObject,
        formats: list[str] | None = None,
        output_directory: Path | str | None = None,
        stop_on_error: bool = True,
    ) -> EngineResult:
        """
        Ejecuta las exportaciones solicitadas.

        Args:
            final_project:
                Proyecto consolidado.

            formats:
                Formatos solicitados. Por defecto:
                markdown y json.

            output_directory:
                Carpeta de salida opcional. Cuando se omite:
                <proyecto>/06_EXPORTACIONES

            stop_on_error:
                Si es True, detiene la ejecución cuando un
                Exporter falla. Si es False, intenta continuar.

        Returns:
            EngineResult con FinalProjectObject actualizado.
        """

        try:
            validation_result = self._validate(
                final_project
            )

            if validation_result is not None:
                return validation_result

            resolved_formats = self._resolve_formats(
                formats
            )

            if not resolved_formats:
                return EngineResult.fail(
                    message=(
                        "No se resolvió ningún formato "
                        "de exportación válido."
                    ),
                    errors=[
                        "La lista de formatos está vacía."
                    ],
                    metadata=self._base_metadata(
                        final_project
                    ),
                )

            export_directory = self._resolve_output_directory(
                final_project=final_project,
                output_directory=output_directory,
            )

            export_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            executions: list[ExportExecution] = []
            warnings: list[str] = []
            errors: list[str] = []

            for export_format in resolved_formats:
                execution = self._execute_exporter(
                    export_format=export_format,
                    final_project=final_project,
                    output_directory=export_directory,
                )

                executions.append(
                    execution
                )

                warnings.extend(
                    execution.warnings
                )

                if not execution.success:
                    errors.extend(
                        execution.errors
                        or [
                            (
                                "Falló la exportación "
                                f"'{export_format}'."
                            )
                        ]
                    )

                    if stop_on_error:
                        break

            successful_executions = [
                execution
                for execution in executions
                if execution.success
            ]

            failed_executions = [
                execution
                for execution in executions
                if not execution.success
            ]

            self._update_project_metadata(
                final_project=final_project,
                output_directory=export_directory,
                executions=executions,
            )

            execution_data = [
                self._execution_to_dict(
                    execution
                )
                for execution in executions
            ]

            metadata = {
                **self._base_metadata(
                    final_project
                ),
                "output_directory": str(
                    export_directory
                ),
                "requested_formats": resolved_formats,
                "executed_formats": [
                    execution.export_format
                    for execution in executions
                ],
                "successful_formats": [
                    execution.export_format
                    for execution in successful_executions
                ],
                "failed_formats": [
                    execution.export_format
                    for execution in failed_executions
                ],
                "exports_count": len(
                    final_project.exports
                ),
                "stop_on_error": stop_on_error,
                "executions": execution_data,
            }

            if failed_executions:
                return EngineResult.fail(
                    message=(
                        "Una o más exportaciones "
                        "no pudieron completarse."
                    ),
                    errors=errors,
                    warnings=warnings,
                    metadata=metadata,
                )

            return EngineResult.ok(
                data=final_project,
                message=(
                    "Exportaciones del proyecto "
                    "generadas correctamente."
                ),
                warnings=warnings,
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en ExportEngine."
                ),
                errors=[
                    str(error)
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

    def register_exporter(
        self,
        export_format: str,
        exporter: Any,
    ) -> None:
        """
        Registra o reemplaza un Exporter.

        El Exporter debe implementar:

            execute(
                final_project,
                output_directory,
            ) -> EngineResult
        """

        normalized_format = self._normalize_format(
            export_format
        )

        if normalized_format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                "Formato no soportado por ExportEngine: "
                f"{export_format}"
            )

        if exporter is None:
            raise ValueError(
                "exporter no puede ser None."
            )

        execute_method = getattr(
            exporter,
            "execute",
            None,
        )

        if not callable(
            execute_method
        ):
            raise TypeError(
                "El Exporter debe implementar execute()."
            )

        self._exporters[
            normalized_format
        ] = exporter

    def available_formats(
        self,
    ) -> list[str]:
        """
        Devuelve los formatos declarados por el Engine.
        """

        return sorted(
            self.SUPPORTED_FORMATS
        )

    def registered_formats(
        self,
    ) -> list[str]:
        """
        Devuelve los Exporters ya cargados.
        """

        return sorted(
            self._exporters
        )

    # --------------------------------------------------
    # Validación
    # --------------------------------------------------

    def _validate(
        self,
        final_project: FinalProjectObject,
    ) -> EngineResult | None:
        """
        Comprueba que el proyecto pueda exportarse.
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
                    "ExportEngine requiere un "
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
                    "de exportarse."
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

        if final_project.metrics is None:
            return EngineResult.fail(
                message=(
                    "El proyecto debe calcular sus métricas "
                    "antes de exportarse."
                ),
                errors=[
                    "FinalProjectObject.metrics es None."
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        if final_project.manifest is None:
            return EngineResult.fail(
                message=(
                    "El proyecto debe generar su manifiesto "
                    "antes de exportarse."
                ),
                errors=[
                    "FinalProjectObject.manifest es None."
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        return None

    # --------------------------------------------------
    # Resolución de formatos y rutas
    # --------------------------------------------------

    def _resolve_formats(
        self,
        formats: list[str] | None,
    ) -> list[str]:
        """
        Normaliza formatos, elimina duplicados y conserva orden.
        """

        requested_formats = (
            formats
            if formats is not None
            else self.DEFAULT_FORMATS
        )

        if not isinstance(
            requested_formats,
            list,
        ):
            raise TypeError(
                "formats debe ser una lista o None."
            )

        resolved: list[str] = []

        for value in requested_formats:
            normalized = self._normalize_format(
                value
            )

            if normalized not in self.SUPPORTED_FORMATS:
                raise ValueError(
                    "Formato de exportación no soportado: "
                    f"{value}"
                )

            if normalized not in resolved:
                resolved.append(
                    normalized
                )

        return resolved

    def _normalize_format(
        self,
        export_format: Any,
    ) -> str:
        """
        Convierte alias de formato a un identificador oficial.
        """

        normalized = str(
            export_format or ""
        ).strip().lower()

        return self.FORMAT_ALIASES.get(
            normalized,
            normalized,
        )

    def _resolve_output_directory(
        self,
        final_project: FinalProjectObject,
        output_directory: Path | str | None,
    ) -> Path:
        """
        Resuelve la carpeta de exportaciones.
        """

        if output_directory is None:
            return (
                Path(
                    final_project.project.path
                )
                / self.DEFAULT_EXPORT_DIRECTORY
            )

        path = Path(
            output_directory
        ).expanduser()

        if not path.is_absolute():
            path = (
                Path(
                    final_project.project.path
                )
                / path
            )

        return path.resolve()

    # --------------------------------------------------
    # Ejecución de Exporters
    # --------------------------------------------------

    def _execute_exporter(
        self,
        export_format: str,
        final_project: FinalProjectObject,
        output_directory: Path,
    ) -> ExportExecution:
        """
        Ejecuta un Exporter y normaliza su resultado.
        """

        try:
            exporter = self._get_exporter(
                export_format
            )

            result = exporter.execute(
                final_project=final_project,
                output_directory=output_directory,
            )

            if not isinstance(
                result,
                EngineResult,
            ):
                return ExportExecution(
                    export_format=export_format,
                    success=False,
                    message=(
                        "El Exporter devolvió un "
                        "resultado incompatible."
                    ),
                    errors=[
                        (
                            "Se esperaba EngineResult y se "
                            f"recibió {type(result).__name__}."
                        )
                    ],
                )

            output_path = self._extract_output_path(
                export_format=export_format,
                result=result,
                final_project=final_project,
            )

            if result.success and not output_path:
                return ExportExecution(
                    export_format=export_format,
                    success=False,
                    message=(
                        "El Exporter informó éxito, pero "
                        "no devolvió una ruta de salida."
                    ),
                    warnings=list(
                        result.warnings
                    ),
                    errors=[
                        "output_path no disponible."
                    ],
                    metadata=dict(
                        result.metadata
                    ),
                )

            if result.success:
                final_project.register_export(
                    export_format,
                    output_path,
                )

            return ExportExecution(
                export_format=export_format,
                success=result.success,
                message=result.message,
                output_path=output_path,
                warnings=list(
                    result.warnings
                ),
                errors=list(
                    result.errors
                ),
                metadata=dict(
                    result.metadata
                ),
            )

        except Exception as error:
            return ExportExecution(
                export_format=export_format,
                success=False,
                message=(
                    f"Falló el Exporter '{export_format}'."
                ),
                errors=[
                    str(error)
                ],
                metadata={
                    "exception_type": (
                        error.__class__.__name__
                    ),
                },
            )

    def _get_exporter(
        self,
        export_format: str,
    ) -> Any:
        """
        Devuelve un Exporter registrado o lo carga de forma diferida.
        """

        if export_format in self._exporters:
            return self._exporters[
                export_format
            ]

        exporter = self._build_default_exporter(
            export_format
        )

        self.register_exporter(
            export_format=export_format,
            exporter=exporter,
        )

        return exporter

    def _build_default_exporter(
        self,
        export_format: str,
    ) -> Any:
        """
        Importa el Exporter solo cuando se necesita.

        Esto permite compilar ExportEngine antes de crear
        todos los Exporters concretos.
        """

        if export_format == "markdown":
            from markdown_exporter import (
                MarkdownExporter,
            )

            return MarkdownExporter()

        if export_format == "json":
            from json_exporter import (
                JSONExporter,
            )

            return JSONExporter()

        if export_format == "zip":
            from zip_exporter import (
                ZIPExporter,
            )

            return ZIPExporter()

        raise ValueError(
            "No existe un Exporter predeterminado para: "
            f"{export_format}"
        )

    def _extract_output_path(
        self,
        export_format: str,
        result: EngineResult,
        final_project: FinalProjectObject,
    ) -> str:
        """
        Extrae la ruta de salida del resultado del Exporter.
        """

        metadata_path = result.metadata.get(
            "output_path"
        )

        if metadata_path:
            return str(
                metadata_path
            )

        if isinstance(
            result.data,
            dict,
        ):
            data_path = result.data.get(
                "output_path"
            )

            if data_path:
                return str(
                    data_path
                )

        registered_path = (
            final_project.exports.get(
                export_format,
                "",
            )
        )

        return str(
            registered_path
        ).strip()

    # --------------------------------------------------
    # Metadatos
    # --------------------------------------------------

    def _update_project_metadata(
        self,
        final_project: FinalProjectObject,
        output_directory: Path,
        executions: list[ExportExecution],
    ) -> None:
        """
        Registra el estado consolidado de exportación.
        """

        final_project.metadata[
            "export_engine"
        ] = {
            "executed": True,
            "version": self.VERSION,
            "output_directory": str(
                output_directory
            ),
            "formats": [
                execution.export_format
                for execution in executions
            ],
            "successful_formats": [
                execution.export_format
                for execution in executions
                if execution.success
            ],
            "failed_formats": [
                execution.export_format
                for execution in executions
                if not execution.success
            ],
            "exports": dict(
                final_project.exports
            ),
        }

    def _execution_to_dict(
        self,
        execution: ExportExecution,
    ) -> dict[str, Any]:
        """
        Convierte ExportExecution a un diccionario serializable.
        """

        return {
            "format": execution.export_format,
            "success": execution.success,
            "message": execution.message,
            "output_path": execution.output_path,
            "warnings": list(
                execution.warnings
            ),
            "errors": list(
                execution.errors
            ),
            "metadata": dict(
                execution.metadata
            ),
        }

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
            "project_path": str(
                project.path
            ),
            "project_stage": project.stage_actual,
            "default_output_directory": (
                self.DEFAULT_EXPORT_DIRECTORY
            ),
            "supported_formats": (
                self.available_formats()
            ),
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
            "default_output_directory": (
                self.DEFAULT_EXPORT_DIRECTORY
            ),
            "default_formats": list(
                self.DEFAULT_FORMATS
            ),
            "supported_formats": (
                self.available_formats()
            ),
            "registered_formats": (
                self.registered_formats()
            ),
            "writes_files": False,
            "orchestrates_exporters": True,
            "requires_finalized_project": True,
            "requires_manifest": True,
            "requires_metrics": True,
            "next_component": (
                "markdown_exporter"
            ),
        }