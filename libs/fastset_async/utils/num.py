from __future__ import annotations

import re
from typing import Any

_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def parse_int_maybe_hex(value: Any) -> int:
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if s.startswith(("0x", "0X")):
        return int(s, 16)
    if s.isdigit():
        return int(s, 10)
    if _HEX_RE.fullmatch(s):
        return int(s, 16)
    try:
        return int(s, 10)
    except ValueError:
        return int(s, 16)


def to_hex_noprefix(value: int | str) -> str:
    if isinstance(value, int):
        return format(value, "x")
    s = str(value).strip().lower()
    if s.startswith("0x"):
        return s[2:]
    if s.isdigit():
        return format(int(s, 10), "x")
    if _HEX_RE.fullmatch(s):
        return s
    raise ValueError("invalid numeric value")


def _hex_noprefix(b: bytes) -> str:
    return b.hex()
