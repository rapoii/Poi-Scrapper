"""Stub intent parser — rule-based, deterministic.

Phase 1.1: kita pakai regex + keyword map untuk extract entity + scope dari
prompt user. Tujuannya supaya UI bisa di-test tanpa LLM. Phase 1.2 akan ganti
implementation ini dengan provider LLM real (Gemini default).

Public API: `IntentParser.parse(prompt) -> Plan`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from loguru import logger

from app.schemas.intent import Intent, IntentField, IntentFilter, Plan, TargetScope
from app.services.intent_parser_llm import build_llm_parser
from app.services.llm.base import LLMUnavailableError


class IntentParserProtocol(Protocol):
    """Interface yang akan di-implement Phase 1.2 (LLM-backed)."""

    async def parse(self, prompt: str) -> Plan:
        """Turn natural-language prompt → structured Plan."""
        ...


# ---- Entity templates -----------------------------------------------------
# Mapping keyword (id + en) → (entity_type slug, default fields).
# Daftar field reflect "reasonable defaults" supaya user nggak harus lengkapin
# manual; di Phase 1.2 LLM bakal expand/refine berdasarkan konteks RS / kota.

_FIELD_TEMPLATES: dict[str, list[IntentField]] = {
    "doctor": [
        IntentField(name="nama", label="Nama Lengkap", data_type="string"),
        IntentField(name="gelar", label="Gelar", data_type="string", required=False),
        IntentField(name="spesialisasi", label="Spesialisasi", data_type="string"),
        IntentField(
            name="sub_spesialisasi",
            label="Sub-spesialisasi",
            data_type="string",
            required=False,
        ),
        IntentField(name="str_no", label="Nomor STR", data_type="string", required=False),
        IntentField(name="sip_no", label="Nomor SIP", data_type="string", required=False),
        IntentField(
            name="jadwal_praktik",
            label="Jadwal Praktik",
            data_type="array",
            required=False,
        ),
        IntentField(name="poli", label="Poli / Departemen", data_type="string", required=False),
        IntentField(name="email", label="Email", data_type="email", required=False),
        IntentField(name="telepon", label="Telepon", data_type="phone", required=False),
        IntentField(name="profile_url", label="URL Profil", data_type="url", required=False),
    ],
    "restaurant": [
        IntentField(name="nama", label="Nama Restoran", data_type="string"),
        IntentField(name="alamat", label="Alamat", data_type="string"),
        IntentField(name="kota", label="Kota", data_type="string"),
        IntentField(name="kategori", label="Kategori Masakan", data_type="string", required=False),
        IntentField(name="rating", label="Rating", data_type="number", required=False),
        IntentField(name="jam_buka", label="Jam Buka", data_type="string", required=False),
        IntentField(name="telepon", label="Telepon", data_type="phone", required=False),
        IntentField(name="website", label="Website", data_type="url", required=False),
        IntentField(name="foto_url", label="URL Foto", data_type="url", required=False),
    ],
    "school": [
        IntentField(name="nama", label="Nama Sekolah", data_type="string"),
        IntentField(name="jenjang", label="Jenjang", data_type="string"),
        IntentField(name="alamat", label="Alamat", data_type="string"),
        IntentField(name="kota", label="Kota", data_type="string"),
        IntentField(name="akreditasi", label="Akreditasi", data_type="string", required=False),
        IntentField(name="npsn", label="NPSN", data_type="string", required=False),
        IntentField(name="telepon", label="Telepon", data_type="phone", required=False),
        IntentField(name="website", label="Website", data_type="url", required=False),
    ],
    "company": [
        IntentField(name="nama", label="Nama Perusahaan", data_type="string"),
        IntentField(name="industri", label="Industri", data_type="string", required=False),
        IntentField(name="alamat", label="Alamat", data_type="string", required=False),
        IntentField(name="kota", label="Kota", data_type="string", required=False),
        IntentField(name="website", label="Website", data_type="url", required=False),
        IntentField(name="email", label="Email", data_type="email", required=False),
        IntentField(name="telepon", label="Telepon", data_type="phone", required=False),
        IntentField(name="ukuran", label="Ukuran Perusahaan", data_type="string", required=False),
    ],
    "hotel": [
        IntentField(name="nama", label="Nama Hotel", data_type="string"),
        IntentField(name="alamat", label="Alamat", data_type="string"),
        IntentField(name="kota", label="Kota", data_type="string"),
        IntentField(name="bintang", label="Rating Bintang", data_type="number", required=False),
        IntentField(name="harga_mulai", label="Harga Mulai", data_type="number", required=False),
        IntentField(name="fasilitas", label="Fasilitas", data_type="array", required=False),
        IntentField(name="website", label="Website", data_type="url", required=False),
    ],
    "generic": [
        IntentField(name="nama", label="Nama", data_type="string"),
        IntentField(name="deskripsi", label="Deskripsi", data_type="string", required=False),
        IntentField(name="url", label="URL", data_type="url", required=False),
    ],
}

# Mapping keyword → entity slug. Order penting: yang lebih spesifik dulu.
# Pakai `\w*` di akhir kata bahasa Inggris supaya plural ("doctors", "schools") match.
_ENTITY_KEYWORDS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(dokter|doctors?|physicians?|spesialis)\b", re.IGNORECASE), "doctor"),
    (
        re.compile(r"\b(restoran|restaurants?|cafes?|kafe|kuliner|warung|warteg)\b", re.IGNORECASE),
        "restaurant",
    ),
    (
        re.compile(r"\b(sekolah|schools?|smp|sma|sd|tk|smk|madrasah)\b", re.IGNORECASE),
        "school",
    ),
    (re.compile(r"\b(hotels?|penginapan|resorts?|villas?)\b", re.IGNORECASE), "hotel"),
    (
        re.compile(
            r"\b(perusahaan|compan(?:y|ies)|startups?|firma|pt|cv)\b",
            re.IGNORECASE,
        ),
        "company",
    ),
]

# Pattern untuk institution: "di RS X", "di Universitas Y", dll.
_INSTITUTION_PATTERN = re.compile(
    r"\b(?:di|at|on|in)\s+"
    r"((?:RS(?:UD|UP|UI)?|Hospital|Universitas|University|Sekolah|School|Mall|Hotel|"
    r"Plaza|Tower|Apartemen|Apartment|Klinik|Clinic|Puskesmas)\s+[A-Z][\w.\s-]+?)"
    r"(?:[,.\s]|$)",
)
# Pattern lokasi: "di Jakarta", "in Bandung", "Surabaya".
_LOCATION_PATTERN = re.compile(
    r"\b(?:di|at|in|kota|city of)\s+"
    r"(Jakarta|Bandung|Surabaya|Medan|Semarang|Yogyakarta|Yogya|Jogja|Bali|Denpasar|"
    r"Makassar|Palembang|Tangerang|Bekasi|Bogor|Depok|Karawaci|Solo|Malang|Batam)\b",
    re.IGNORECASE,
)
# Filter exclusion patterns: "kecuali umum", "exclude general"
_FILTER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(?:exclude|kecuali|tanpa|excluding)\s+(.+?)(?:[.,]|$)", re.IGNORECASE),
        "exclude",
    ),
    (re.compile(r"\b(?:hanya|only)\s+(.+?)(?:[.,]|$)", re.IGNORECASE), "only"),
]
# Bahasa: heuristic — adanya kata id-spesifik → "id".
_ID_KEYWORDS = re.compile(
    r"\b(saya|aku|mau|gue|gw|tolong|carikan|buatin|data|dari|untuk|di|ke|tentang)\b",
    re.IGNORECASE,
)


@dataclass
class StubIntentParser:
    """Rule-based parser; replace di Phase 1.2 dengan LLM-backed implementation."""

    async def parse(self, prompt: str) -> Plan:
        cleaned = prompt.strip()
        if not cleaned:
            msg = "prompt is empty"
            raise ValueError(msg)

        entity_type = self._detect_entity(cleaned)
        institution = self._extract_institution(cleaned)
        location = self._extract_location(cleaned)
        filters = self._extract_filters(cleaned)
        language = "id" if _ID_KEYWORDS.search(cleaned) else "en"

        fields = list(_FIELD_TEMPLATES.get(entity_type, _FIELD_TEMPLATES["generic"]))

        entity_label_parts = [entity_type.replace("_", " ").title()]
        if institution:
            entity_label_parts.append(f"di {institution}")
        elif location:
            entity_label_parts.append(f"di {location.title()}")

        intent = Intent(
            entity_type=entity_type,
            entity_label=" ".join(entity_label_parts),
            target_scope=TargetScope(
                institution=institution,
                location=location.title() if location else None,
                country="ID" if language == "id" else None,
            ),
            required_fields=fields,
            filters=filters,
            language=language,
            notes=(
                "Parsed by StubIntentParser (rule-based). "
                "Akan di-upgrade ke Gemini di Phase 1.2 untuk akurasi field & filter."
            ),
        )

        return Plan(
            intent=intent,
            sources=[],
            estimated_record_count=None,
            warnings=(
                ["Stub parser tidak bisa infer field domain-spesifik di luar template."]
                if entity_type == "generic"
                else []
            ),
        )

    @staticmethod
    def _detect_entity(prompt: str) -> str:
        for pattern, slug in _ENTITY_KEYWORDS:
            if pattern.search(prompt):
                return slug
        return "generic"

    @staticmethod
    def _extract_institution(prompt: str) -> str | None:
        match = _INSTITUTION_PATTERN.search(prompt)
        if not match:
            return None
        return match.group(1).strip(" ,.")

    @staticmethod
    def _extract_location(prompt: str) -> str | None:
        match = _LOCATION_PATTERN.search(prompt)
        if not match:
            return None
        return match.group(1).strip()

    @staticmethod
    def _extract_filters(prompt: str) -> list[IntentFilter]:
        filters: list[IntentFilter] = []
        for pattern, kind in _FILTER_PATTERNS:
            for match in pattern.finditer(prompt):
                expr = match.group(0).strip()
                value = match.group(1).strip()
                op = "not_contains" if kind == "exclude" else "contains"
                filters.append(IntentFilter(op=op, value=value, expression=expr))
        return filters


def get_intent_parser() -> IntentParserProtocol:
    """FastAPI dependency: pilih parser sesuai env + ketersediaan API key.

    Resolution order:
      1. LLM provider (Gemini / OpenRouter / dst) kalau API key tersedia.
      2. Fallback ke `StubIntentParser` (rule-based) supaya app tetap usable
         tanpa LLM (dev mode, CI, offline).
    """
    try:
        parser = build_llm_parser()
        logger.info(
            "Intent parser: LLM provider={} model={}",
            parser.provider.name,
            parser.provider.model,
        )
        return parser
    except LLMUnavailableError as exc:
        logger.warning("LLM provider unavailable, fallback ke stub parser: {}", exc)
        return StubIntentParser()
