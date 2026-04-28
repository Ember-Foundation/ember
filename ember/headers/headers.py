"""
HTTP headers container with case-insensitive lookup.
In production this file is compiled by Cython via headers.pxd.
"""
from __future__ import annotations
from typing import Iterator


class Headers:
    """Immutable, case-insensitive HTTP header container.

    Backed by a flat list of (name, value) byte pairs for low allocation cost
    during parsing. Lookup builds a dict lazily on first access.
    """

    __slots__ = ("_raw", "_index")

    def __init__(self, raw: list[tuple[bytes, bytes]]) -> None:
        self._raw = raw
        self._index: dict[bytes, bytes] | None = None

    def _build_index(self) -> None:
        self._index = {k.lower(): v for k, v in self._raw}

    def get(self, name: bytes, default: bytes | None = None) -> bytes | None:
        if self._index is None:
            self._build_index()
        return self._index.get(name.lower(), default)

    def get_str(self, name: str, default: str | None = None) -> str | None:
        value = self.get(name.encode(), None)
        if value is None:
            return default
        return value.decode("latin-1")

    def __contains__(self, name: bytes) -> bool:
        if self._index is None:
            self._build_index()
        return name.lower() in self._index

    def __iter__(self) -> Iterator[tuple[bytes, bytes]]:
        return iter(self._raw)

    def __len__(self) -> int:
        return len(self._raw)

    def to_dict(self) -> dict[str, str]:
        return {k.decode("latin-1"): v.decode("latin-1") for k, v in self._raw}

    def serialize(self) -> bytes:
        return b"".join(k + b": " + v + b"\r\n" for k, v in self._raw)
