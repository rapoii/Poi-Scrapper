"""Static HTML scraper with LLM-assisted extraction fallback.

The strategy keeps a deterministic heuristic path for local/offline runs, then
uses the configured LLM provider when available to extract multiple records from
one source page.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.intent import Intent, IntentField
from app.services.llm import LLMError, LLMProvider, LLMUnavailableError, get_llm_provider
from app.services.scraper.base import ScrapedRecordDraft

_MAX_TEXT_CHARS = 12000
_MAX_LLM_RECORDS = 100
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)


class NeedsHeadlessError(RuntimeError):
    """Raised when static HTML looks like an unrendered JS app shell."""


ExtractedValue = str | int | float | bool | list[str] | None


class ExtractedCell(BaseModel):
    """One field value returned by the extraction LLM."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    value: ExtractedValue = None
    confidence: float = Field(default=0.75, ge=0, le=1)


class ExtractedRecord(BaseModel):
    """One extracted entity row."""

    model_config = ConfigDict(extra="forbid")

    fields: list[ExtractedCell] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Structured LLM extraction payload."""

    model_config = ConfigDict(extra="forbid")

    records: list[ExtractedRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StaticHtmlScraper:
    """Fetch static HTML and extract records."""

    def __init__(
        self,
        *,
        timeout_s: float = 20.0,
        llm_provider: LLMProvider | None = None,
        use_llm_extraction: bool = True,
    ) -> None:
        self._timeout_s = timeout_s
        self._llm_provider = llm_provider
        self._use_llm_extraction = use_llm_extraction

    async def scrape(
        self,
        *,
        url: str,
        title: str | None,
        reliability_score: float | None,
        intent: Intent,
    ) -> list[ScrapedRecordDraft]:
        html_text = await self._fetch_html(url=url, title=title, intent=intent)
        return await self.scrape_html(
            html_text=html_text,
            url=url,
            title=title,
            reliability_score=reliability_score,
            intent=intent,
            allow_headless_signal=True,
        )

    async def scrape_html(
        self,
        *,
        html_text: str,
        url: str,
        title: str | None,
        reliability_score: float | None,
        intent: Intent,
        allow_headless_signal: bool = False,
    ) -> list[ScrapedRecordDraft]:
        """Extract records from an already-fetched HTML document."""
        page = _extract_page_text(html_text)
        if allow_headless_signal and _looks_js_rendered(html_text=html_text, text=page.text):
            raise NeedsHeadlessError("static HTML looks like a JavaScript-rendered shell")

        page_title = title or page.title or urlparse(url).netloc or url
        if self._use_llm_extraction and urlparse(url).netloc != "example.com":
            llm_records = await self._extract_with_llm(
                intent=intent,
                source_url=url,
                source_title=page_title,
                reliability_score=reliability_score,
                text=page.text,
            )
            if llm_records:
                return llm_records

        return [
            _heuristic_record(
                intent=intent,
                source_url=url,
                source_title=page_title,
                reliability_score=reliability_score,
                text=page.text,
            )
        ]

    async def _fetch_html(self, *, url: str, title: str | None, intent: Intent) -> str:
        parsed = urlparse(url)
        if parsed.netloc == "example.com":
            label = intent.entity_label or intent.entity_type.title()
            return (
                "<html><head>"
                f"<title>{html.escape(title or label)}</title>"
                "</head><body>"
                f"<h1>{html.escape(label)}</h1>"
                f"<p>{html.escape(intent.notes or 'Synthetic fixture source for tests.')}</p>"
                "</body></html>"
            )

        async with httpx.AsyncClient(
            timeout=self._timeout_s,
            follow_redirects=True,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        ) as client:
            resp = await client.get(url)
            _raise_for_blocked_response(resp)
            return resp.text

    async def _extract_with_llm(
        self,
        *,
        intent: Intent,
        source_url: str,
        source_title: str,
        reliability_score: float | None,
        text: str,
    ) -> list[ScrapedRecordDraft]:
        provider = self._resolve_llm_provider()
        if provider is None or not text:
            return []

        try:
            result = await provider.generate_structured(
                system_prompt=_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=_build_extraction_prompt(
                    intent=intent,
                    source_url=source_url,
                    source_title=source_title,
                    text=text,
                ),
                response_schema=ExtractionResult,
                temperature=0.0,
                max_tokens=4096,
            )
        except LLMError as exc:
            logger.warning("LLM record extraction failed for {}: {}", source_url, exc)
            return []

        return _records_from_llm_result(
            result=result,
            intent=intent,
            source_url=source_url,
            reliability_score=reliability_score,
        )

    def _resolve_llm_provider(self) -> LLMProvider | None:
        if self._llm_provider is not None:
            return self._llm_provider
        try:
            return get_llm_provider()
        except LLMUnavailableError:
            return None


_EXTRACTION_SYSTEM_PROMPT = """\
You extract structured records from visible webpage text for PoiScrapper.

Rules:
- Return only JSON matching the schema.
- Extract every distinct entity row visible in the text, up to 100 records.
- Use field names exactly as requested.
- Do not invent values. Use null when a value is missing.
- Respect filters in the intent. Exclude records that clearly violate filters.
- Use confidence 0..1 per field.
"""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self._in_title = False
        self._title_chunks: list[str] = []
        self._text_chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._in_title = True
        if lowered in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._in_title = False
            self.title = _normalize_text(" ".join(self._title_chunks)) or None
        if lowered in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_chunks.append(data)
        if self._skip_depth == 0:
            self._text_chunks.append(data)

    @property
    def text(self) -> str:
        return _normalize_text(" ".join(self._text_chunks))[:_MAX_TEXT_CHARS]


def _extract_page_text(html_text: str) -> _TextExtractor:
    parser = _TextExtractor()
    parser.feed(html_text)
    return parser


def _raise_for_blocked_response(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    if _is_cloudflare_challenge(resp):
        msg = (
            f"Access blocked by Cloudflare challenge (HTTP {resp.status_code}). "
            "Pilih source publik lain, official API, atau halaman yang mengizinkan scraping."
        )
        raise RuntimeError(msg)
    if resp.status_code in {401, 403}:
        msg = (
            f"Access denied by source site (HTTP {resp.status_code}). "
            "Pilih source publik lain atau aktifkan source yang memang bisa diakses tanpa login."
        )
        raise RuntimeError(msg)
    if resp.status_code == 429:
        msg = "Source rate-limited the scraper (HTTP 429). Coba lagi nanti atau pilih source lain."
        raise RuntimeError(msg)
    resp.raise_for_status()


def _is_cloudflare_challenge(resp: httpx.Response) -> bool:
    if resp.headers.get("cf-mitigated", "").lower() == "challenge":
        return True
    text = resp.text[:4000].lower()
    return "challenges.cloudflare.com" in text or "cf-mitigated" in text


def _heuristic_record(
    *,
    intent: Intent,
    source_url: str,
    source_title: str,
    reliability_score: float | None,
    text: str,
) -> ScrapedRecordDraft:
    data = _build_record_data(
        intent=intent,
        source_url=source_url,
        source_title=source_title,
        text=text,
    )
    completeness = _completeness_score(intent.required_fields, data)
    confidence = _confidence_score(
        completeness=completeness,
        field_confidence=None,
        reliability_score=reliability_score,
    )
    confidences = {
        field.name: confidence if _is_filled(data.get(field.name)) else 0.0
        for field in intent.required_fields
    }
    return ScrapedRecordDraft(
        data=data,
        field_confidences=confidences,
        source_url=source_url,
        completeness_score=completeness,
        confidence_score=confidence,
        fingerprint=_fingerprint(url=source_url, data=data),
    )


def _build_record_data(
    *,
    intent: Intent,
    source_url: str,
    source_title: str,
    text: str,
) -> dict[str, object]:
    data: dict[str, object] = {}
    scope = intent.target_scope
    location = scope.location or scope.institution or scope.country

    for field in intent.required_fields:
        data[field.name] = _value_for_field(
            field=field,
            intent=intent,
            source_url=source_url,
            source_title=source_title,
            text=text,
            location=location,
        )
    return data


def _value_for_field(  # noqa: PLR0911
    *,
    field: IntentField,
    intent: Intent,
    source_url: str,
    source_title: str,
    text: str,
    location: str | None,
) -> object:
    name = field.name.lower()
    label = (intent.entity_label or intent.entity_type).strip()

    if name in {"url", "profile_url", "website", "source_url"} or field.data_type == "url":
        return source_url
    if name in {"nama", "name", "title"}:
        return source_title or label
    if name in {"alamat", "address", "kota", "city", "location"}:
        return location or _first_sentence(text)
    if name in {"spesialisasi", "specialty", "kategori", "category"}:
        return _extract_specialty(intent) or label
    if field.data_type == "array":
        return [_first_sentence(text) or source_title]
    if field.data_type == "number":
        return _first_number(text)
    if field.data_type == "boolean":
        return True
    if field.data_type in {"email", "phone"}:
        return None if not field.required else _first_sentence(text)
    return _first_sentence(text) or source_title or label


def _records_from_llm_result(
    *,
    result: ExtractionResult,
    intent: Intent,
    source_url: str,
    reliability_score: float | None,
) -> list[ScrapedRecordDraft]:
    drafts: list[ScrapedRecordDraft] = []
    for extracted in result.records[:_MAX_LLM_RECORDS]:
        cells = {cell.name: cell for cell in extracted.fields}
        data: dict[str, object] = {}
        confidences: dict[str, float] = {}

        for field in intent.required_fields:
            cell = cells.get(field.name)
            value = _coerce_extracted_value(cell.value if cell else None, field)
            data[field.name] = value
            confidences[field.name] = (
                round(cell.confidence, 3) if cell and _is_filled(value) else 0.0
            )

        if not any(_is_filled(value) for value in data.values()):
            continue

        completeness = _completeness_score(intent.required_fields, data)
        field_confidence = _avg([score for score in confidences.values() if score > 0])
        confidence = _confidence_score(
            completeness=completeness,
            field_confidence=field_confidence,
            reliability_score=reliability_score,
        )
        drafts.append(
            ScrapedRecordDraft(
                data=data,
                field_confidences=confidences,
                source_url=source_url,
                completeness_score=completeness,
                confidence_score=confidence,
                fingerprint=_fingerprint(url=source_url, data=data),
            )
        )
    return drafts


def _build_extraction_prompt(
    *,
    intent: Intent,
    source_url: str,
    source_title: str,
    text: str,
) -> str:
    field_specs = [
        {
            "name": field.name,
            "label": field.label,
            "data_type": field.data_type,
            "required": field.required,
            "description": field.description,
        }
        for field in intent.required_fields
    ]
    payload = {
        "source_url": source_url,
        "source_title": source_title,
        "entity_type": intent.entity_type,
        "entity_label": intent.entity_label,
        "target_scope": intent.target_scope.model_dump(mode="json"),
        "fields": field_specs,
        "filters": [item.model_dump(mode="json") for item in intent.filters],
        "visible_text": text[:_MAX_TEXT_CHARS],
    }
    return json.dumps(payload, ensure_ascii=False)


def _coerce_extracted_value(value: ExtractedValue, field: IntentField) -> object:  # noqa: PLR0911
    if value is None:
        return None
    if field.data_type == "array":
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [part.strip() for part in str(value).split(",") if part.strip()]
    if field.data_type == "number":
        if isinstance(value, (int, float)):
            return float(value)
        return _first_number(str(value))
    if field.data_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "ya", "y"}
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip() or None


def _looks_js_rendered(*, html_text: str, text: str) -> bool:
    lowered = html_text.lower()
    text_len = len(text.strip())
    script_count = lowered.count("<script")
    app_shell_signals = (
        'id="__next"' in lowered
        or "window.__initial_state__" in lowered
        or "data-reactroot" in lowered
        or "ng-version" in lowered
    )
    return text_len < 250 and (script_count >= 4 or app_shell_signals)


def _extract_specialty(intent: Intent) -> str | None:
    text = " ".join(
        part
        for part in [
            intent.entity_label or "",
            intent.notes or "",
            *[f.expression for f in intent.filters],
        ]
        if part
    )
    match = re.search(r"(jantung|cardio\w*|hotel|restaurant|school|sekolah)", text, re.I)
    return match.group(1) if match else None


def _first_sentence(text: str) -> str | None:
    if not text:
        return None
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return sentence[:240] if sentence else None


def _first_number(text: str) -> float | None:
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def _completeness_score(fields: list[IntentField], data: dict[str, object]) -> float:
    required = [field for field in fields if field.required]
    if not required:
        return 1.0
    filled = sum(1 for field in required if _is_filled(data.get(field.name)))
    return round(filled / len(required), 3)


def _confidence_score(
    *,
    completeness: float,
    field_confidence: float | None,
    reliability_score: float | None,
) -> float:
    reliability = reliability_score if reliability_score is not None else 0.45
    extraction = field_confidence if field_confidence is not None else completeness
    return round(min(0.98, (0.45 * completeness) + (0.35 * extraction) + (0.2 * reliability)), 3)


def _fingerprint(*, url: str, data: dict[str, object]) -> str:
    raw = json.dumps({"url": url, "data": data}, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _is_filled(value: object) -> bool:
    if value is None:
        return False
    if value == "":
        return False
    return value != []


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)
