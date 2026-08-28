"""Free Wikimedia Commons image acquisition through the PM8 provider boundary."""

from __future__ import annotations

import html
import json
import re
import struct
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from media_provider import MediaProvider, MediaRequest, MediaResult

from .models import AssetBinary, MediaFamily


WIKIMEDIA_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIMEDIA_PROVIDER_NAME = "wikimedia_commons"
DEFAULT_USER_AGENT = "CIPS/PM9.1 (https://github.com/RayIA007/CIPS)"

JsonFetcher = Callable[[str], Mapping[str, Any]]
BytesFetcher = Callable[[str], bytes]

_SUPPORTED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
_ALLOWED_LICENSE_MARKERS = (
    "cc by",
    "cc0",
    "creative commons attribution",
    "public domain",
    "pdm",
    "gfdl",
    "free art license",
)
_DISALLOWED_LICENSE_MARKERS = (
    "all rights reserved",
    "copyrighted",
    "fair use",
    "non-free",
    "no known restrictions",
    "-nc",
    "-nd",
)
_HTML_TAG = re.compile(r"<[^>]+>")


class WikimediaCommonsProvider(MediaProvider):
    """Acquire freely licensed raster images without credentials or billing.

    The provider performs one Commons Action API search and downloads the first
    deterministic candidate whose declared license and physical bytes satisfy
    the configured policy.  Network functions are injectable so tests never
    contact Wikimedia.
    """

    provider_name = WIKIMEDIA_PROVIDER_NAME
    capability_name = "stock_image_search"

    def __init__(
        self,
        *,
        api_endpoint: str = WIKIMEDIA_COMMONS_API,
        user_agent: str = DEFAULT_USER_AGENT,
        fetch_json: JsonFetcher | None = None,
        fetch_bytes: BytesFetcher | None = None,
        timeout_seconds: float = 20.0,
        max_download_bytes: int = 25_000_000,
        min_width: int = 640,
        min_height: int = 360,
        min_aspect_ratio: float = 0.25,
        max_aspect_ratio: float = 4.0,
        search_limit: int = 8,
    ) -> None:
        self.api_endpoint = _validated_https_url(
            api_endpoint,
            allowed_hosts={"commons.wikimedia.org"},
            label="api_endpoint",
        )
        self.user_agent = str(user_agent).strip()
        if not self.user_agent:
            raise ValueError("user_agent no puede estar vacío.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser positivo.")
        if max_download_bytes < 1024:
            raise ValueError("max_download_bytes debe ser al menos 1024.")
        if min_width < 1 or min_height < 1:
            raise ValueError("Las dimensiones mínimas deben ser positivas.")
        if min_aspect_ratio <= 0 or max_aspect_ratio < min_aspect_ratio:
            raise ValueError("El rango de aspecto permitido es inválido.")
        if not 1 <= search_limit <= 50:
            raise ValueError("search_limit debe estar entre 1 y 50.")

        self.timeout_seconds = float(timeout_seconds)
        self.max_download_bytes = int(max_download_bytes)
        self.min_width = int(min_width)
        self.min_height = int(min_height)
        self.min_aspect_ratio = float(min_aspect_ratio)
        self.max_aspect_ratio = float(max_aspect_ratio)
        self.search_limit = int(search_limit)
        self._fetch_json = fetch_json or self._default_fetch_json
        self._fetch_bytes = fetch_bytes or self._default_fetch_bytes
        if not callable(self._fetch_json) or not callable(self._fetch_bytes):
            raise TypeError("fetch_json y fetch_bytes deben ser callables.")
        self.calls: list[MediaRequest] = []

    def capabilities(self) -> dict[str, dict[str, Any]]:
        return {
            self.capability_name: {
                "available": True,
                "cost_tier": "free",
                "free_tier": True,
                "license": "commons_free_license_required",
                "priority": 20,
                "quality_tier": "standard",
                "source": "wikimedia_commons_action_api",
            }
        }

    def estimate_cost(self, request: MediaRequest) -> float | None:
        del request
        return 0.0

    def generate(self, request: MediaRequest) -> MediaResult:
        errors = self.validate_input(request)
        if errors:
            return MediaResult.fail(errors=errors)
        if not isinstance(request.payload, Mapping):
            return MediaResult.fail(errors=["payload debe ser Mapping."])
        query = _request_query(request.payload)
        if query is None:
            return MediaResult.fail(
                message="Wikimedia Commons requiere stock_query o prompt.",
                errors=["missing_stock_query"],
                metadata={"provider": self.provider_name},
            )

        try:
            search_url = self._search_url(query)
            payload = self._fetch_json(search_url)
            candidates = self._candidates(payload)
        except Exception as error:
            return self._failure("commons_search_failed", error)

        rejected: list[str] = []
        for candidate in candidates:
            title = str(candidate.get("title") or "unknown")
            contract = _candidate_contract(candidate)
            if isinstance(contract, str):
                rejected.append(f"{title}:{contract}")
                continue
            try:
                content = self._fetch_bytes(contract["delivery_uri"])
                if not isinstance(content, bytes) or not content:
                    raise ValueError("La descarga no devolvió bytes no vacíos.")
                if len(content) > self.max_download_bytes:
                    raise ValueError("La imagen excede max_download_bytes.")
                width, height = image_dimensions(content, contract["mime_type"])
                if width != contract["width"] or height != contract["height"]:
                    raise ValueError(
                        "Las dimensiones físicas no coinciden con Wikimedia."
                    )
                if width < self.min_width or height < self.min_height:
                    raise ValueError("La imagen no alcanza las dimensiones mínimas.")
                aspect_ratio = width / height
                if not self.min_aspect_ratio <= aspect_ratio <= self.max_aspect_ratio:
                    raise ValueError("La imagen tiene una relación de aspecto extrema.")
                output = AssetBinary(
                    content=content,
                    mime_type=contract["mime_type"],
                    file_extension=contract["file_extension"],
                    media_family=MediaFamily.IMAGE,
                    delivery_uri=contract["delivery_uri"],
                    actual_cost_usd=0.0,
                    metadata={
                        "actual_cost_usd": 0.0,
                        "aspect_ratio": round(aspect_ratio, 8),
                        "attribution": contract["attribution"],
                        "creator": contract["creator"],
                        "description_url": contract["source_url"],
                        "downloaded_size_bytes": len(content),
                        "height_px": height,
                        "license_name": contract["license_name"],
                        "license_url": contract["license_url"],
                        "page_id": contract["page_id"],
                        "prompt_permitted": query,
                        "selected_title": contract["title"],
                        "source_url": contract["source_url"],
                        "stock_query": query,
                        "width_px": width,
                    },
                )
            except Exception as error:
                rejected.append(f"{title}:{type(error).__name__}:{error}")
                continue

            self.calls.append(request)
            return MediaResult.ok(
                output,
                message="Imagen libre adquirida desde Wikimedia Commons.",
                metadata={
                    "provider": self.provider_name,
                    "capability": self.capability_name,
                    "selected_title": contract["title"],
                },
            )

        return MediaResult.fail(
            message="Wikimedia Commons no devolvió una imagen elegible.",
            errors=rejected[: self.search_limit] or ["no_commons_candidates"],
            metadata={"provider": self.provider_name, "stock_query": query},
        )

    def _search_url(self, query: str) -> str:
        parameters = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrnamespace": "6",
            "gsrsearch": f"{query} filetype:bitmap",
            "gsrlimit": str(self.search_limit),
            "prop": "imageinfo",
            "iiprop": "url|mime|size|mediatype|extmetadata",
            "iiextmetadatalanguage": "en",
            "iiextmetadatafilter": (
                "Artist|Credit|LicenseShortName|LicenseUrl|UsageTerms"
            ),
        }
        return f"{self.api_endpoint}?{urlencode(parameters)}"

    def _candidates(self, payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(payload, Mapping):
            raise TypeError("La respuesta de Wikimedia debe ser Mapping.")
        query = payload.get("query")
        if not isinstance(query, Mapping):
            return ()
        pages = query.get("pages")
        if not isinstance(pages, list):
            return ()
        candidates = [item for item in pages if isinstance(item, Mapping)]
        return tuple(
            sorted(
                candidates,
                key=lambda item: (
                    int(item.get("index") or 10**9),
                    int(item.get("pageid") or 0),
                    str(item.get("title") or ""),
                ),
            )
        )

    def _default_fetch_json(self, url: str) -> Mapping[str, Any]:
        content = self._http_get(url, max_bytes=2_000_000)
        payload = json.loads(content.decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("Wikimedia no devolvió un JSON object.")
        return payload

    def _default_fetch_bytes(self, url: str) -> bytes:
        _validated_https_url(
            url,
            allowed_hosts={"upload.wikimedia.org"},
            label="delivery_uri",
        )
        return self._http_get(url, max_bytes=self.max_download_bytes)

    def _http_get(self, url: str, *, max_bytes: int) -> bytes:
        request = Request(
            url,
            headers={
                "Accept": "application/json,image/jpeg,image/png;q=0.9,*/*;q=0.1",
                "User-Agent": self.user_agent,
            },
            method="GET",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            final_host = urlsplit(response.geturl()).hostname
            if final_host not in {
                "commons.wikimedia.org",
                "upload.wikimedia.org",
            }:
                raise ValueError("Wikimedia redirigió a un host no permitido.")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise ValueError("La respuesta excede el límite de bytes.")
            content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError("La respuesta excede el límite de bytes.")
        return content

    def _failure(self, code: str, error: Exception) -> MediaResult:
        return MediaResult.fail(
            message="Wikimedia Commons no pudo completar la adquisición.",
            errors=[f"{code}:{type(error).__name__}:{error}"],
            metadata={"provider": self.provider_name},
        )


def image_dimensions(content: bytes, mime_type: str) -> tuple[int, int]:
    """Read PNG/JPEG dimensions from physical bytes without optional packages."""

    normalized = str(mime_type).strip().lower()
    if normalized == "image/png":
        if (
            len(content) < 24
            or not content.startswith(b"\x89PNG\r\n\x1a\n")
            or content[12:16] != b"IHDR"
        ):
            raise ValueError("PNG sin encabezado IHDR válido.")
        width, height = struct.unpack(">II", content[16:24])
        if width < 1 or height < 1:
            raise ValueError("PNG con dimensiones inválidas.")
        return width, height

    if normalized != "image/jpeg" or not content.startswith(b"\xff\xd8\xff"):
        raise ValueError("Sólo se aceptan PNG o JPEG físicos.")
    offset = 2
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while offset + 3 < len(content):
        if content[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(content) and content[offset] == 0xFF:
            offset += 1
        if offset >= len(content):
            break
        marker = content[offset]
        offset += 1
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(content):
            break
        segment_length = int.from_bytes(content[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(content):
            raise ValueError("JPEG con segmento truncado.")
        if marker in sof_markers:
            if segment_length < 7:
                raise ValueError("JPEG con SOF inválido.")
            height = int.from_bytes(content[offset + 3 : offset + 5], "big")
            width = int.from_bytes(content[offset + 5 : offset + 7], "big")
            if width < 1 or height < 1:
                raise ValueError("JPEG con dimensiones inválidas.")
            return width, height
        offset += segment_length
    raise ValueError("JPEG sin marcador SOF de dimensiones.")


def _request_query(payload: Mapping[str, Any]) -> str | None:
    for key in ("stock_query", "prompt", "creative_brief"):
        value = str(payload.get(key) or "").strip()
        if value:
            return " ".join(value.split())[:500]
    return None


def _candidate_contract(candidate: Mapping[str, Any]) -> dict[str, Any] | str:
    imageinfo = candidate.get("imageinfo")
    if not isinstance(imageinfo, list) or len(imageinfo) != 1:
        return "imageinfo_invalido"
    info = imageinfo[0]
    if not isinstance(info, Mapping):
        return "imageinfo_invalido"
    mime_type = str(info.get("mime") or "").strip().lower()
    extension = _SUPPORTED_MIME_TYPES.get(mime_type)
    if extension is None:
        return "mime_no_soportado"
    if str(info.get("mediatype") or "").strip().upper() != "BITMAP":
        return "mediatype_no_bitmap"
    try:
        width = int(info.get("width"))
        height = int(info.get("height"))
        page_id = int(candidate.get("pageid"))
    except (TypeError, ValueError):
        return "dimensiones_o_pageid_invalidos"
    if width < 1 or height < 1:
        return "dimensiones_invalidas"
    try:
        delivery_uri = _validated_https_url(
            info.get("url"),
            allowed_hosts={"upload.wikimedia.org"},
            label="delivery_uri",
        )
        source_url = _validated_https_url(
            info.get("descriptionurl"),
            allowed_hosts={"commons.wikimedia.org"},
            label="source_url",
        )
    except (TypeError, ValueError):
        return "url_insegura"

    metadata = info.get("extmetadata")
    if not isinstance(metadata, Mapping):
        return "extmetadata_ausente"
    license_name = _metadata_text(metadata, "LicenseShortName") or _metadata_text(
        metadata, "UsageTerms"
    )
    normalized_license = license_name.casefold()
    if not license_name or any(
        marker in normalized_license for marker in _DISALLOWED_LICENSE_MARKERS
    ):
        return "licencia_rechazada"
    if not any(marker in normalized_license for marker in _ALLOWED_LICENSE_MARKERS):
        return "licencia_no_permitida"
    license_url = _metadata_text(metadata, "LicenseUrl")
    if license_url:
        try:
            license_url = _validated_https_url(
                license_url,
                allowed_hosts=None,
                label="license_url",
            )
        except (TypeError, ValueError):
            return "license_url_insegura"
    creator = _metadata_text(metadata, "Artist") or _metadata_text(metadata, "Credit")
    public_domain = any(
        marker in normalized_license for marker in ("cc0", "public domain", "pdm")
    )
    if not creator and not public_domain:
        return "atribucion_ausente"
    attribution = creator or "Wikimedia Commons; obra declarada de dominio público."
    title = str(candidate.get("title") or "").strip()
    if not title:
        return "title_ausente"
    return {
        "attribution": attribution,
        "creator": creator or "",
        "delivery_uri": delivery_uri,
        "file_extension": extension,
        "height": height,
        "license_name": license_name,
        "license_url": license_url,
        "mime_type": mime_type,
        "page_id": page_id,
        "source_url": source_url,
        "title": title,
        "width": width,
    }


def _metadata_text(metadata: Mapping[str, Any], key: str) -> str:
    raw = metadata.get(key)
    if isinstance(raw, Mapping):
        raw = raw.get("value")
    text = html.unescape(_HTML_TAG.sub(" ", str(raw or "")))
    return " ".join(text.split())[:1000]


def _validated_https_url(
    value: Any,
    *,
    allowed_hosts: set[str] | None,
    label: str,
) -> str:
    normalized = str(value or "").strip()
    parsed = urlsplit(normalized)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or (allowed_hosts is not None and parsed.hostname not in allowed_hosts)
    ):
        raise ValueError(f"{label} debe ser una URL HTTPS pública permitida.")
    return normalized


__all__ = [
    "DEFAULT_USER_AGENT",
    "WIKIMEDIA_COMMONS_API",
    "WIKIMEDIA_PROVIDER_NAME",
    "WikimediaCommonsProvider",
    "image_dimensions",
]
