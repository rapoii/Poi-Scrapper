"""ULID-based identifier helpers.

ULIDs = 128-bit sortable, URL-safe, lexicographically sortable by time.
Kita simpan sebagai PostgreSQL `uuid` (16-byte) lewat `UUID(bytes=...)` —
ULID dan UUID sama-sama 128-bit jadi lossless. Stringified version (`new_id_str`)
pakai format ULID base32 (26 char) untuk trace_id supaya lebih ringkas dari UUID.
"""

from __future__ import annotations

from uuid import UUID

from ulid import ULID


def new_id() -> UUID:
    """Return a new ULID-backed UUID (sortable by time, kompatibel kolom uuid Postgres)."""
    return UUID(bytes=ULID().bytes)


def new_id_str() -> str:
    """Return stringified ULID (26-char base32) — bagus untuk trace_id."""
    return str(ULID())
