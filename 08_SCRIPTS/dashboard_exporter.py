"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 085
Archivo  : dashboard_exporter.py
Estado   : RELEASE
=========================================================

Exporta ExecutiveDashboard a formatos persistentes.

Formatos:
- EXECUTIVE_DASHBOARD.json
- EXECUTIVE_DASHBOARD.md
- EXECUTIVE_DASHBOARD.html

Responsabilidades:
- validar el modelo de entrada;
- persistir JSON de forma atómica;
- renderizar Markdown;
- renderizar HTML autónomo;
- escapar contenido dinámico;
- devolver EngineResult con rutas y metadatos.

Este módulo NO:
- genera los datos del Dashboard;
- lee reportes fuente;
- ejecuta el Pipeline;
- llama proveedores;
- aplica optimizaciones;
- depende de recursos web externos.
"""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any

from dashboard_models import (
    DashboardCard,
    DashboardChart,
    DashboardChartType,
    DashboardSection,
    DashboardStatus,
    ExecutiveDashboard,
)
from runtime_models import EngineResult


class DashboardExporter:
    """
    Exportador desacoplado del Executive Dashboard.
    """

    COMPONENT_NAME = "dashboard_exporter"
    VERSION = "0.9"

    DEFAULT_OUTPUT_DIRECTORY = "03_TELEMETRIA"

    JSON_FILENAME = "EXECUTIVE_DASHBOARD.json"
    MARKDOWN_FILENAME = "EXECUTIVE_DASHBOARD.md"
    HTML_FILENAME = "EXECUTIVE_DASHBOARD.html"

    def execute(
        self,
        *,
        dashboard: ExecutiveDashboard,
        project_path: Path | str,
        output_directory: Path | str | None = None,
        export_json: bool = True,
        export_markdown: bool = True,
        export_html: bool = True,
    ) -> EngineResult:
        """
        Exporta el Dashboard a los formatos seleccionados.
        """

        try:
            if not isinstance(
                dashboard,
                ExecutiveDashboard,
            ):
                return EngineResult.fail(
                    message=(
                        "DashboardExporter requiere un "
                        "ExecutiveDashboard válido."
                    ),
                    errors=[
                        "Tipo de dashboard incompatible."
                    ],
                    metadata={
                        "component": self.COMPONENT_NAME,
                        "version": self.VERSION,
                    },
                )

            resolved_project_path = Path(
                project_path
            ).expanduser().resolve()

            resolved_output_directory = (
                self._resolve_output_directory(
                    project_path=resolved_project_path,
                    output_directory=output_directory,
                )
            )

            resolved_output_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            paths = {
                "json_path": "",
                "markdown_path": "",
                "html_path": "",
            }

            if export_json:
                json_path = (
                    resolved_output_directory
                    / self.JSON_FILENAME
                )

                self._write_text_atomic(
                    json_path,
                    json.dumps(
                        dashboard.to_dict(),
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                )

                paths["json_path"] = str(
                    json_path
                )

            if export_markdown:
                markdown_path = (
                    resolved_output_directory
                    / self.MARKDOWN_FILENAME
                )

                self._write_text_atomic(
                    markdown_path,
                    self.render_markdown(
                        dashboard
                    ),
                )

                paths["markdown_path"] = str(
                    markdown_path
                )

            if export_html:
                html_path = (
                    resolved_output_directory
                    / self.HTML_FILENAME
                )

                self._write_text_atomic(
                    html_path,
                    self.render_html(
                        dashboard
                    ),
                )

                paths["html_path"] = str(
                    html_path
                )

            exported_formats = [
                name
                for name, enabled in {
                    "json": export_json,
                    "markdown": export_markdown,
                    "html": export_html,
                }.items()
                if enabled
            ]

            warnings: list[str] = []

            if not exported_formats:
                warnings.append(
                    "No se seleccionó ningún formato "
                    "de exportación."
                )

            return EngineResult.ok(
                data={
                    "dashboard": dashboard,
                    "paths": paths,
                    "exported_formats": (
                        exported_formats
                    ),
                },
                message=(
                    "Executive Dashboard exportado "
                    "correctamente."
                ),
                warnings=warnings,
                metadata={
                    "component": self.COMPONENT_NAME,
                    "version": self.VERSION,
                    "project_id": dashboard.project_id,
                    "dashboard_id": (
                        dashboard.dashboard_id
                    ),
                    "status": dashboard.status.value,
                    "output_directory": str(
                        resolved_output_directory
                    ),
                    "exported_formats": (
                        exported_formats
                    ),
                    "files_created": sum(
                        bool(
                            value
                        )
                        for value in paths.values()
                    ),
                    **paths,
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado al exportar "
                    "el Executive Dashboard."
                ),
                errors=[
                    str(
                        error
                    )
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                    "version": self.VERSION,
                    "exception_type": (
                        error.__class__.__name__
                    ),
                },
            )

    def render_markdown(
        self,
        dashboard: ExecutiveDashboard,
    ) -> str:
        """
        Renderiza el Dashboard en Markdown.
        """

        self._validate_dashboard(
            dashboard
        )

        lines: list[str] = [
            f"# {dashboard.title}",
            "",
            f"**Proyecto:** {dashboard.project_id}",
            f"**Generado:** {dashboard.generated_at}",
            f"**Estado:** {dashboard.status.value}",
            "",
            "## Resumen ejecutivo",
            "",
            (
                dashboard.executive_summary
                or (
                    "No existe un resumen ejecutivo "
                    "disponible."
                )
            ),
            "",
            "## Indicadores principales",
            "",
            "| Indicador | Valor | Estado | Tendencia |",
            "|---|---:|---|---|",
        ]

        visible_cards = dashboard.visible_cards()

        if visible_cards:
            for card in visible_cards:
                lines.append(
                    (
                        f"| {card.title} "
                        f"| {self._format_card_value(card)} "
                        f"| {card.status.value} "
                        f"| {card.trend} |"
                    )
                )
        else:
            lines.append(
                "| Sin indicadores | — | UNKNOWN | UNKNOWN |"
            )

        lines.extend(
            [
                "",
                "## Visualizaciones",
                "",
            ]
        )

        visible_charts = dashboard.visible_charts()

        if visible_charts:
            for chart in visible_charts:
                lines.extend(
                    self._render_chart_markdown(
                        chart
                    )
                )
        else:
            lines.append(
                "No existen visualizaciones disponibles."
            )

        lines.extend(
            [
                "",
                "## Secciones",
                "",
            ]
        )

        visible_sections = dashboard.visible_sections()

        if visible_sections:
            for section in visible_sections:
                lines.extend(
                    self._render_section_markdown(
                        section
                    )
                )
        else:
            lines.append(
                "No existen secciones disponibles."
            )

        if dashboard.warnings:
            lines.extend(
                [
                    "",
                    "## Advertencias",
                    "",
                    *[
                        f"- {warning}"
                        for warning in dashboard.warnings
                    ],
                ]
            )

        if dashboard.errors:
            lines.extend(
                [
                    "",
                    "## Errores",
                    "",
                    *[
                        f"- {error}"
                        for error in dashboard.errors
                    ],
                ]
            )

        lines.append(
            ""
        )

        return "\n".join(
            lines
        )

    def render_html(
        self,
        dashboard: ExecutiveDashboard,
    ) -> str:
        """
        Renderiza un HTML autónomo y responsivo.
        """

        self._validate_dashboard(
            dashboard
        )

        dashboard_payload = json.dumps(
            dashboard.to_dict(),
            ensure_ascii=False,
        ).replace(
            "</",
            "<\\/",
        )

        cards_html = "".join(
            self._render_card_html(
                card
            )
            for card in dashboard.visible_cards()
        )

        charts_html = "".join(
            self._render_chart_html(
                chart
            )
            for chart in dashboard.visible_charts()
        )

        sections_html = "".join(
            self._render_section_html(
                section
            )
            for section in dashboard.visible_sections()
        )

        warnings_html = self._render_messages_html(
            title="Advertencias",
            values=dashboard.warnings,
            css_class="warning-panel",
        )

        errors_html = self._render_messages_html(
            title="Errores",
            values=dashboard.errors,
            css_class="error-panel",
        )

        status_class = self._status_css_class(
            dashboard.status
        )

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(dashboard.title)} — {escape(dashboard.project_id)}</title>
<style>
:root {{
  color-scheme: light dark;
  --bg: #f3f5f8;
  --surface: #ffffff;
  --surface-alt: #eef1f5;
  --text: #172033;
  --muted: #667085;
  --border: #d9dee8;
  --excellent: #177245;
  --good: #2563a6;
  --attention: #a56400;
  --critical: #b42318;
  --unknown: #667085;
  --shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}}

@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #111827;
    --surface: #1f2937;
    --surface-alt: #273449;
    --text: #f3f4f6;
    --muted: #c0c7d1;
    --border: #3b4658;
    --shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
  }}
}}

* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system,
    BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
}}

.dashboard-shell {{
  width: min(1500px, calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0 48px;
}}

.hero {{
  display: grid;
  gap: 18px;
  padding: 28px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: var(--surface);
  box-shadow: var(--shadow);
}}

.hero-top {{
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  flex-wrap: wrap;
}}

.eyebrow {{
  margin: 0 0 6px;
  color: var(--muted);
  font-size: 0.84rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}}

h1, h2, h3 {{
  margin-top: 0;
}}

h1 {{
  margin-bottom: 5px;
  font-size: clamp(1.8rem, 4vw, 3rem);
}}

.project-meta {{
  color: var(--muted);
}}

.status-pill {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 7px 13px;
  border-radius: 999px;
  color: #fff;
  font-size: 0.84rem;
  font-weight: 750;
  letter-spacing: 0.04em;
}}

.status-excellent {{
  background: var(--excellent);
}}

.status-good {{
  background: var(--good);
}}

.status-attention {{
  background: var(--attention);
}}

.status-critical {{
  background: var(--critical);
}}

.status-unknown {{
  background: var(--unknown);
}}

.summary {{
  max-width: 1050px;
  margin: 0;
  font-size: 1.04rem;
}}

.section-block {{
  margin-top: 28px;
}}

.section-heading {{
  margin-bottom: 14px;
}}

.cards-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 16px;
}}

.dashboard-card {{
  min-height: 164px;
  padding: 18px;
  border: 1px solid var(--border);
  border-top-width: 5px;
  border-radius: 16px;
  background: var(--surface);
  box-shadow: var(--shadow);
}}

.dashboard-card.status-excellent {{
  border-top-color: var(--excellent);
}}

.dashboard-card.status-good {{
  border-top-color: var(--good);
}}

.dashboard-card.status-attention {{
  border-top-color: var(--attention);
}}

.dashboard-card.status-critical {{
  border-top-color: var(--critical);
}}

.dashboard-card.status-unknown {{
  border-top-color: var(--unknown);
}}

.card-title {{
  margin: 0;
  color: var(--muted);
  font-size: 0.9rem;
  font-weight: 700;
}}

.card-value {{
  margin: 8px 0 4px;
  font-size: clamp(1.65rem, 4vw, 2.45rem);
  font-weight: 800;
  overflow-wrap: anywhere;
}}

.card-subtitle,
.card-description,
.card-recommendation {{
  color: var(--muted);
  font-size: 0.88rem;
}}

.card-footer {{
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-top: 12px;
  color: var(--muted);
  font-size: 0.78rem;
}}

.charts-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
  gap: 18px;
}}

.chart-card {{
  min-height: 300px;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface);
  box-shadow: var(--shadow);
}}

.chart-card canvas {{
  width: 100%;
  height: 235px;
  display: block;
}}

.chart-empty {{
  display: grid;
  place-items: center;
  height: 220px;
  color: var(--muted);
}}

.section-panel {{
  margin-top: 18px;
  padding: 22px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface);
  box-shadow: var(--shadow);
}}

.section-panel summary {{
  cursor: pointer;
  font-size: 1.12rem;
  font-weight: 750;
}}

.section-description {{
  color: var(--muted);
}}

.item-list {{
  padding-left: 20px;
}}

.mini-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
  gap: 12px;
  margin-top: 14px;
}}

.mini-card {{
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-alt);
}}

.message-panel {{
  margin-top: 18px;
  padding: 16px 18px;
  border-radius: 14px;
}}

.warning-panel {{
  border: 1px solid var(--attention);
  background: color-mix(in srgb, var(--attention) 10%, var(--surface));
}}

.error-panel {{
  border: 1px solid var(--critical);
  background: color-mix(in srgb, var(--critical) 10%, var(--surface));
}}

.footer {{
  margin-top: 28px;
  color: var(--muted);
  font-size: 0.82rem;
  text-align: center;
}}

@media (max-width: 620px) {{
  .dashboard-shell {{
    width: min(100% - 18px, 1500px);
    padding-top: 12px;
  }}

  .hero,
  .dashboard-card,
  .chart-card,
  .section-panel {{
    border-radius: 13px;
  }}

  .hero {{
    padding: 20px;
  }}

  .charts-grid {{
    grid-template-columns: 1fr;
  }}
}}

@media print {{
  body {{
    background: #fff;
    color: #111;
  }}

  .dashboard-shell {{
    width: 100%;
    padding: 0;
  }}

  .hero,
  .dashboard-card,
  .chart-card,
  .section-panel {{
    box-shadow: none;
    break-inside: avoid;
  }}
}}
</style>
</head>
<body>
<main class="dashboard-shell">
  <header class="hero">
    <div class="hero-top">
      <div>
        <p class="eyebrow">CIPS Executive Analytics</p>
        <h1>{escape(dashboard.title)}</h1>
        <div class="project-meta">
          Proyecto: <strong>{escape(dashboard.project_id)}</strong><br>
          Generado: {escape(dashboard.generated_at)}
        </div>
      </div>
      <span class="status-pill {status_class}">
        {escape(dashboard.status.value)}
      </span>
    </div>
    <p class="summary">{escape(
        dashboard.executive_summary
        or "No existe un resumen ejecutivo disponible."
    )}</p>
  </header>

  <section class="section-block">
    <div class="section-heading">
      <h2>Indicadores principales</h2>
    </div>
    <div class="cards-grid">
      {cards_html or '<p>No existen indicadores visibles.</p>'}
    </div>
  </section>

  <section class="section-block">
    <div class="section-heading">
      <h2>Visualizaciones</h2>
    </div>
    <div class="charts-grid">
      {charts_html or '<p>No existen gráficos visibles.</p>'}
    </div>
  </section>

  <section class="section-block">
    <div class="section-heading">
      <h2>Detalle ejecutivo</h2>
    </div>
    {sections_html or '<p>No existen secciones visibles.</p>'}
  </section>

  {warnings_html}
  {errors_html}

  <footer class="footer">
    Generado por CIPS Dashboard Exporter {escape(self.VERSION)}
  </footer>
</main>

<script id="dashboard-data" type="application/json">
{dashboard_payload}
</script>

<script>
(function () {{
  "use strict";

  const dataElement = document.getElementById("dashboard-data");
  if (!dataElement) return;

  let dashboard;
  try {{
    dashboard = JSON.parse(dataElement.textContent);
  }} catch (error) {{
    console.error("No fue posible leer los datos del Dashboard.", error);
    return;
  }}

  const chartMap = new Map(
    (dashboard.charts || []).map(chart => [chart.chart_id, chart])
  );

  document.querySelectorAll("canvas[data-chart-id]").forEach(canvas => {{
    const chart = chartMap.get(canvas.dataset.chartId);
    if (!chart) return;
    drawChart(canvas, chart);
  }});

  window.addEventListener("resize", debounce(() => {{
    document.querySelectorAll("canvas[data-chart-id]").forEach(canvas => {{
      const chart = chartMap.get(canvas.dataset.chartId);
      if (chart) drawChart(canvas, chart);
    }});
  }}, 120));

  function drawChart(canvas, chart) {{
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(Math.floor(rect.width), 260);
    const height = Math.max(Math.floor(rect.height), 210);
    const ratio = window.devicePixelRatio || 1;

    canvas.width = width * ratio;
    canvas.height = height * ratio;

    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const styles = getComputedStyle(document.documentElement);
    const text = styles.getPropertyValue("--text").trim() || "#172033";
    const muted = styles.getPropertyValue("--muted").trim() || "#667085";
    const border = styles.getPropertyValue("--border").trim() || "#d9dee8";

    const palette = ["#2563a6", "#177245", "#a56400", "#b42318",
      "#7c3aed", "#0891b2", "#be185d", "#4f46e5"];

    ctx.font = "12px system-ui";
    ctx.fillStyle = text;
    ctx.strokeStyle = border;
    ctx.lineWidth = 1;

    const type = String(chart.chart_type || "TABLE").toUpperCase();

    if (type === "DONUT" || type === "PIE") {{
      drawPie(ctx, chart, width, height, palette, text, muted, type);
      return;
    }}

    if (type === "RADAR") {{
      drawRadar(ctx, chart, width, height, palette, text, muted, border);
      return;
    }}

    if (type === "GAUGE") {{
      drawGauge(ctx, chart, width, height, palette, text, muted, border);
      return;
    }}

    drawCartesian(ctx, chart, width, height, palette, text, muted, border);
  }}

  function drawCartesian(ctx, chart, width, height, palette, text, muted, border) {{
    const pad = {{ left: 48, right: 18, top: 28, bottom: 48 }};
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
    const labels = chart.labels?.length
      ? chart.labels
      : chart.series?.[0]?.labels || [];
    const allValues = (chart.series || []).flatMap(series => series.values || []);
    const maxValue = Math.max(1, ...allValues.map(Number));
    const minValue = Math.min(0, ...allValues.map(Number));
    const span = Math.max(maxValue - minValue, 1);

    ctx.strokeStyle = border;
    ctx.fillStyle = muted;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";

    for (let index = 0; index <= 4; index++) {{
      const y = pad.top + (plotH * index / 4);
      const value = maxValue - (span * index / 4);
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();
      ctx.fillText(formatNumber(value), pad.left - 7, y);
    }}

    if (!labels.length || !(chart.series || []).length) {{
      ctx.textAlign = "center";
      ctx.fillText("Sin datos", width / 2, height / 2);
      return;
    }}

    const type = String(chart.chart_type || "BAR").toUpperCase();
    const seriesCount = chart.series.length;
    const groupWidth = plotW / labels.length;

    chart.series.forEach((series, seriesIndex) => {{
      const values = series.values || [];
      const color = palette[seriesIndex % palette.length];
      ctx.strokeStyle = color;
      ctx.fillStyle = color;

      if (type === "LINE" || type === "AREA" || type === "TIMELINE") {{
        ctx.beginPath();
        values.forEach((rawValue, index) => {{
          const value = Number(rawValue) || 0;
          const x = pad.left + groupWidth * (index + 0.5);
          const y = pad.top + plotH * (1 - ((value - minValue) / span));
          if (index === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }});

        if (type === "AREA") {{
          const lastX = pad.left + groupWidth * (values.length - 0.5);
          ctx.lineTo(lastX, pad.top + plotH);
          ctx.lineTo(pad.left + groupWidth * 0.5, pad.top + plotH);
          ctx.closePath();
          ctx.globalAlpha = 0.22;
          ctx.fill();
          ctx.globalAlpha = 1;
          ctx.beginPath();
          values.forEach((rawValue, index) => {{
            const value = Number(rawValue) || 0;
            const x = pad.left + groupWidth * (index + 0.5);
            const y = pad.top + plotH * (1 - ((value - minValue) / span));
            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }});
        }}

        ctx.lineWidth = 2;
        ctx.stroke();

        values.forEach((rawValue, index) => {{
          const value = Number(rawValue) || 0;
          const x = pad.left + groupWidth * (index + 0.5);
          const y = pad.top + plotH * (1 - ((value - minValue) / span));
          ctx.beginPath();
          ctx.arc(x, y, 3.2, 0, Math.PI * 2);
          ctx.fill();
        }});
      }} else {{
        const barGap = Math.max(3, groupWidth * 0.08);
        const available = groupWidth - (barGap * 2);
        const barWidth = Math.max(
          4,
          available / Math.max(seriesCount, 1) - 3
        );

        values.forEach((rawValue, index) => {{
          const value = Number(rawValue) || 0;
          const normalized = (value - minValue) / span;
          const barHeight = Math.max(plotH * normalized, 1);
          const x = pad.left + groupWidth * index + barGap
            + seriesIndex * (barWidth + 3);
          const y = pad.top + plotH - barHeight;
          ctx.fillRect(x, y, barWidth, barHeight);
        }});
      }}
    }});

    ctx.fillStyle = muted;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";

    labels.forEach((label, index) => {{
      const x = pad.left + groupWidth * (index + 0.5);
      const shortLabel = String(label).length > 13
        ? String(label).slice(0, 12) + "…"
        : String(label);
      ctx.fillText(shortLabel, x, height - pad.bottom + 10);
    }});

    drawLegend(ctx, chart.series || [], width, palette, text);
  }}

  function drawPie(ctx, chart, width, height, palette, text, muted, type) {{
    const series = chart.series?.[0];
    const values = (series?.values || []).map(Number);
    const labels = series?.labels || chart.labels || [];
    const total = values.reduce((sum, value) => sum + Math.max(value, 0), 0);
    const radius = Math.min(width, height) * 0.31;
    const centerX = width * 0.38;
    const centerY = height * 0.52;
    let angle = -Math.PI / 2;

    if (total <= 0) {{
      ctx.fillStyle = muted;
      ctx.textAlign = "center";
      ctx.fillText("Sin datos", width / 2, height / 2);
      return;
    }}

    values.forEach((value, index) => {{
      const slice = Math.max(value, 0) / total * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.arc(centerX, centerY, radius, angle, angle + slice);
      ctx.closePath();
      ctx.fillStyle = palette[index % palette.length];
      ctx.fill();
      angle += slice;
    }});

    if (type === "DONUT") {{
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius * 0.54, 0, Math.PI * 2);
      ctx.fillStyle = getComputedStyle(document.documentElement)
        .getPropertyValue("--surface").trim() || "#ffffff";
      ctx.fill();
      ctx.fillStyle = text;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = "700 18px system-ui";
      ctx.fillText(formatNumber(total), centerX, centerY);
    }}

    ctx.font = "12px system-ui";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";

    labels.forEach((label, index) => {{
      const y = 40 + index * 24;
      ctx.fillStyle = palette[index % palette.length];
      ctx.fillRect(width * 0.72, y - 6, 11, 11);
      ctx.fillStyle = text;
      ctx.fillText(
        `${{String(label)}}: ${{formatNumber(values[index] || 0)}}`,
        width * 0.72 + 17,
        y
      );
    }});
  }}

  function drawRadar(ctx, chart, width, height, palette, text, muted, border) {{
    const series = chart.series?.[0];
    const values = (series?.values || []).map(Number);
    const labels = series?.labels || chart.labels || [];
    const count = labels.length;
    const centerX = width / 2;
    const centerY = height / 2 + 8;
    const radius = Math.min(width, height) * 0.32;
    const maxValue = Number(chart.options?.maximum) || 100;

    if (count < 3) {{
      ctx.fillStyle = muted;
      ctx.textAlign = "center";
      ctx.fillText("Datos insuficientes", width / 2, height / 2);
      return;
    }}

    ctx.strokeStyle = border;
    ctx.fillStyle = muted;
    ctx.font = "11px system-ui";

    for (let ring = 1; ring <= 4; ring++) {{
      ctx.beginPath();
      for (let index = 0; index < count; index++) {{
        const angle = -Math.PI / 2 + index * Math.PI * 2 / count;
        const ringRadius = radius * ring / 4;
        const x = centerX + Math.cos(angle) * ringRadius;
        const y = centerY + Math.sin(angle) * ringRadius;
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }}
      ctx.closePath();
      ctx.stroke();
    }}

    labels.forEach((label, index) => {{
      const angle = -Math.PI / 2 + index * Math.PI * 2 / count;
      const x = centerX + Math.cos(angle) * radius;
      const y = centerY + Math.sin(angle) * radius;
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.lineTo(x, y);
      ctx.stroke();

      const labelX = centerX + Math.cos(angle) * (radius + 18);
      const labelY = centerY + Math.sin(angle) * (radius + 18);
      ctx.fillStyle = muted;
      ctx.textAlign = labelX < centerX - 5
        ? "right"
        : labelX > centerX + 5
          ? "left"
          : "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(label), labelX, labelY);
    }});

    ctx.beginPath();
    values.forEach((value, index) => {{
      const angle = -Math.PI / 2 + index * Math.PI * 2 / count;
      const normalized = Math.max(0, Math.min(value / maxValue, 1));
      const x = centerX + Math.cos(angle) * radius * normalized;
      const y = centerY + Math.sin(angle) * radius * normalized;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }});
    ctx.closePath();
    ctx.fillStyle = palette[0] + "44";
    ctx.strokeStyle = palette[0];
    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();
  }}

  function drawGauge(ctx, chart, width, height, palette, text, muted, border) {{
    const value = Number(chart.series?.[0]?.values?.[0]) || 0;
    const maximum = Number(chart.options?.maximum) || 100;
    const ratio = Math.max(0, Math.min(value / maximum, 1));
    const centerX = width / 2;
    const centerY = height * 0.72;
    const radius = Math.min(width, height) * 0.34;

    ctx.lineWidth = 18;
    ctx.lineCap = "round";

    ctx.beginPath();
    ctx.strokeStyle = border;
    ctx.arc(centerX, centerY, radius, Math.PI, Math.PI * 2);
    ctx.stroke();

    ctx.beginPath();
    ctx.strokeStyle = palette[0];
    ctx.arc(centerX, centerY, radius, Math.PI, Math.PI + Math.PI * ratio);
    ctx.stroke();

    ctx.fillStyle = text;
    ctx.textAlign = "center";
    ctx.font = "700 30px system-ui";
    ctx.fillText(formatNumber(value), centerX, centerY - 12);
    ctx.font = "12px system-ui";
    ctx.fillStyle = muted;
    ctx.fillText(`de ${{formatNumber(maximum)}}`, centerX, centerY + 12);
  }}

  function drawLegend(ctx, series, width, palette, text) {{
    ctx.font = "11px system-ui";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";

    let x = 12;
    const y = 13;

    series.forEach((item, index) => {{
      ctx.fillStyle = palette[index % palette.length];
      ctx.fillRect(x, y - 5, 10, 10);
      x += 15;
      ctx.fillStyle = text;
      ctx.fillText(String(item.name || `Serie ${{index + 1}}`), x, y);
      x += Math.min(
        ctx.measureText(String(item.name || "")).width + 22,
        width * 0.36
      );
    }});
  }}

  function formatNumber(value) {{
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value ?? "");
    return new Intl.NumberFormat("es-MX", {{
      maximumFractionDigits: 4
    }}).format(number);
  }}

  function debounce(fn, wait) {{
    let timeout;
    return function (...args) {{
      clearTimeout(timeout);
      timeout = setTimeout(() => fn.apply(this, args), wait);
    }};
  }}
}})();
</script>
</body>
</html>
"""

    def _render_card_html(
        self,
        card: DashboardCard,
    ) -> str:
        """
        Renderiza una tarjeta individual.
        """

        status_class = self._status_css_class(
            card.status
        )

        subtitle = (
            f'<div class="card-subtitle">{escape(card.subtitle)}</div>'
            if card.subtitle
            else ""
        )

        description = (
            f'<div class="card-description">{escape(card.description)}</div>'
            if card.description
            else ""
        )

        recommendation = (
            (
                '<div class="card-recommendation">'
                f'Recomendación: {escape(card.recommendation)}'
                "</div>"
            )
            if card.recommendation
            else ""
        )

        return (
            f'<article class="dashboard-card {status_class}">'
            f'<p class="card-title">{escape(card.title)}</p>'
            f'<div class="card-value">'
            f'{escape(self._format_card_value(card))}'
            f"</div>"
            f"{subtitle}"
            f"{description}"
            f"{recommendation}"
            '<div class="card-footer">'
            f"<span>{escape(card.status.value)}</span>"
            f"<span>{escape(card.trend)}</span>"
            "</div>"
            "</article>"
        )

    def _render_chart_html(
        self,
        chart: DashboardChart,
    ) -> str:
        """
        Renderiza el contenedor HTML de un gráfico.
        """

        subtitle = (
            f"<p>{escape(chart.subtitle)}</p>"
            if chart.subtitle
            else ""
        )

        if chart.total_points() <= 0:
            body = (
                '<div class="chart-empty">'
                "Sin datos disponibles"
                "</div>"
            )
        else:
            body = (
                f'<canvas data-chart-id="{escape(chart.chart_id)}" '
                f'aria-label="{escape(chart.title)}"></canvas>'
            )

        return (
            '<article class="chart-card">'
            f"<h3>{escape(chart.title)}</h3>"
            f"{subtitle}"
            f"{body}"
            "</article>"
        )

    def _render_section_html(
        self,
        section: DashboardSection,
    ) -> str:
        """
        Renderiza una sección desplegable.
        """

        open_attribute = (
            ""
            if section.collapsed
            else " open"
        )

        description = (
            (
                '<p class="section-description">'
                f"{escape(section.description)}"
                "</p>"
            )
            if section.description
            else ""
        )

        mini_cards = "".join(
            (
                '<div class="mini-card">'
                f"<strong>{escape(card.title)}</strong><br>"
                f"{escape(self._format_card_value(card))}"
                "</div>"
            )
            for card in section.cards
            if card.visible
        )

        items = ""

        if section.items:
            items = (
                '<ul class="item-list">'
                + "".join(
                    f"<li>{escape(item)}</li>"
                    for item in section.items
                )
                + "</ul>"
            )

        chart_names = ""

        visible_chart_names = [
            chart.title
            for chart in section.charts
            if chart.visible
        ]

        if visible_chart_names:
            chart_names = (
                "<p><strong>Visualizaciones relacionadas:</strong> "
                + escape(
                    ", ".join(
                        visible_chart_names
                    )
                )
                + "</p>"
            )

        mini_grid = (
            f'<div class="mini-grid">{mini_cards}</div>'
            if mini_cards
            else ""
        )

        return (
            '<details class="section-panel"'
            f"{open_attribute}>"
            f"<summary>{escape(section.title)} "
            f"— {escape(section.status.value)}</summary>"
            f"{description}"
            f"{mini_grid}"
            f"{items}"
            f"{chart_names}"
            "</details>"
        )

    def _render_chart_markdown(
        self,
        chart: DashboardChart,
    ) -> list[str]:
        """
        Renderiza un gráfico como tabla Markdown.
        """

        lines = [
            f"### {chart.title}",
            "",
            f"- Tipo: {chart.chart_type.value}",
            f"- Estado: {chart.status.value}",
        ]

        if chart.subtitle:
            lines.append(
                f"- Descripción: {chart.subtitle}"
            )

        lines.append(
            ""
        )

        labels = (
            chart.labels
            or (
                chart.series[0].labels
                if chart.series
                else []
            )
        )

        if not labels or not chart.series:
            lines.extend(
                [
                    "Sin datos disponibles.",
                    "",
                ]
            )
            return lines

        header = [
            "Categoría",
            *[
                series.name
                for series in chart.series
            ],
        ]

        lines.append(
            "| "
            + " | ".join(
                header
            )
            + " |"
        )

        lines.append(
            "|"
            + "|".join(
                [
                    "---",
                    *[
                        "---:"
                        for _ in chart.series
                    ],
                ]
            )
            + "|"
        )

        for index, label in enumerate(
            labels
        ):
            row = [
                str(
                    label
                )
            ]

            for series in chart.series:
                value = (
                    series.values[index]
                    if index < len(
                        series.values
                    )
                    else 0
                )

                row.append(
                    self._format_number(
                        value
                    )
                )

            lines.append(
                "| "
                + " | ".join(
                    row
                )
                + " |"
            )

        lines.append(
            ""
        )

        return lines

    def _render_section_markdown(
        self,
        section: DashboardSection,
    ) -> list[str]:
        """
        Renderiza una sección en Markdown.
        """

        lines = [
            f"### {section.title}",
            "",
            f"**Estado:** {section.status.value}",
            "",
        ]

        if section.description:
            lines.extend(
                [
                    section.description,
                    "",
                ]
            )

        if section.cards:
            lines.extend(
                [
                    "| Indicador | Valor | Estado |",
                    "|---|---:|---|",
                ]
            )

            for card in section.cards:
                if card.visible:
                    lines.append(
                        (
                            f"| {card.title} "
                            f"| {self._format_card_value(card)} "
                            f"| {card.status.value} |"
                        )
                    )

            lines.append(
                ""
            )

        if section.items:
            lines.extend(
                [
                    *[
                        f"- {item}"
                        for item in section.items
                    ],
                    "",
                ]
            )

        if section.charts:
            chart_titles = [
                chart.title
                for chart in section.charts
                if chart.visible
            ]

            if chart_titles:
                lines.extend(
                    [
                        (
                            "**Visualizaciones relacionadas:** "
                            + ", ".join(
                                chart_titles
                            )
                        ),
                        "",
                    ]
                )

        return lines

    def _render_messages_html(
        self,
        *,
        title: str,
        values: list[str],
        css_class: str,
    ) -> str:
        """
        Renderiza advertencias o errores.
        """

        if not values:
            return ""

        items = "".join(
            f"<li>{escape(value)}</li>"
            for value in values
        )

        return (
            f'<section class="message-panel {escape(css_class)}">'
            f"<h2>{escape(title)}</h2>"
            f"<ul>{items}</ul>"
            "</section>"
        )

    def _format_card_value(
        self,
        card: DashboardCard,
    ) -> str:
        """
        Formatea valor y unidad.
        """

        value = card.value

        if isinstance(
            value,
            float,
        ):
            formatted = self._format_number(
                value
            )

        elif isinstance(
            value,
            int,
        ):
            formatted = f"{value:,}".replace(
                ",",
                " ",
            )

        else:
            formatted = str(
                value
            )

        return (
            f"{formatted} {card.unit}".strip()
        )

    def _format_number(
        self,
        value: Any,
    ) -> str:
        """
        Formatea números sin ceros innecesarios.
        """

        try:
            number = float(
                value
            )
        except (TypeError, ValueError):
            return str(
                value
            )

        if number.is_integer():
            return str(
                int(
                    number
                )
            )

        return (
            f"{number:.6f}"
            .rstrip(
                "0"
            )
            .rstrip(
                "."
            )
        )

    def _status_css_class(
        self,
        status: DashboardStatus,
    ) -> str:
        """
        Convierte estado a clase CSS.
        """

        return {
            DashboardStatus.EXCELLENT: (
                "status-excellent"
            ),
            DashboardStatus.GOOD: (
                "status-good"
            ),
            DashboardStatus.ATTENTION: (
                "status-attention"
            ),
            DashboardStatus.CRITICAL: (
                "status-critical"
            ),
            DashboardStatus.UNKNOWN: (
                "status-unknown"
            ),
        }[
            DashboardStatus.normalize(
                status
            )
        ]

    def _resolve_output_directory(
        self,
        *,
        project_path: Path,
        output_directory: Path | str | None,
    ) -> Path:
        """
        Resuelve el directorio de salida.
        """

        if output_directory is None:
            return (
                project_path
                / self.DEFAULT_OUTPUT_DIRECTORY
            )

        resolved = Path(
            output_directory
        ).expanduser()

        if not resolved.is_absolute():
            resolved = (
                project_path
                / resolved
            )

        return resolved.resolve()

    def _write_text_atomic(
        self,
        path: Path,
        content: str,
    ) -> None:
        """
        Escribe texto con reemplazo atómico.
        """

        temporary_path = path.with_suffix(
            f"{path.suffix}.tmp"
        )

        temporary_path.write_text(
            content,
            encoding="utf-8",
        )

        temporary_path.replace(
            path
        )

    def _validate_dashboard(
        self,
        dashboard: ExecutiveDashboard,
    ) -> None:
        """
        Valida el modelo requerido.
        """

        if not isinstance(
            dashboard,
            ExecutiveDashboard,
        ):
            raise TypeError(
                "dashboard debe ser ExecutiveDashboard."
            )

    def get_component_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve información pública.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "input_model": "ExecutiveDashboard",
            "output_formats": [
                "JSON",
                "Markdown",
                "HTML",
            ],
            "json_filename": self.JSON_FILENAME,
            "markdown_filename": (
                self.MARKDOWN_FILENAME
            ),
            "html_filename": self.HTML_FILENAME,
            "standalone_html": True,
            "external_dependencies": False,
            "atomic_writes": True,
            "next_component": (
                "dashboard_smoke_test"
            ),
        }