# Inventario de activos PM9

## Estado inicial comprobado

El repositorio base no contiene imágenes, video, voz, música ni efectos físicos reutilizables para este proyecto. Por ello no se autoriza todavía un render real.

## Mezcla planificada

| Escena | Necesidad visual | Tipo universal | Resolución |
|---|---|---|---|
| 1 | Atleta en plancha con temblor visible | `stock_video` | Catálogo aprobado |
| 2 | Ilustración biomédica del tronco | `ai_image` | Catálogo aprobado |
| 3 | Unidades motoras y oscilación de fuerza | `motion_graphic` | Nativa del renderer |
| 4 | Alineación y señales para detenerse | `existing_asset` | Catálogo aprobado como `aligned-plank` |

También se requieren cuatro segmentos de narración, una pista musical instrumental y cuatro efectos breves. En total: doce archivos físicos con URL HTTPS pública estable y un gráfico nativo del renderer.

## Gate del catálogo

Cada entrada debe declarar archivo local, URL HTTPS de entrega, fuente, licencia, atribución y costo real. Se rechazan URLs firmadas, tokens, archivos ausentes, MIME/firma inválidos, costos desconocidos y activos pagados no autorizados.

## Fuentes aprobadas para la construcción

- Escena 1: fotografía de plancha de Shixart1985 en Wikimedia Commons, CC BY 2.0, adaptada localmente a video vertical.
- Escenas 2 y 4: ilustraciones SVG procedurales originales de CIPS.
- Narraciones: Piper local con voz mexicana `es_MX-claude-high`; el model card declara dataset Apache-2.0.
- Música y efectos: síntesis procedural original local de CIPS.

El comando `build-assets` genera y cataloga los doce archivos con costo USD 0. Después de incorporarlos al repositorio, `verify-assets` compara byte a byte cada URL pública con su archivo local. Ninguno de esos comandos usa Creatomate ni publica contenido.

El render Creatomate permanece bloqueado hasta que las doce URL públicas estén verificadas, `prepare` finalice sin bloqueos y exista autorización explícita del límite de créditos.
