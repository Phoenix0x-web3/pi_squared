from __future__ import annotations

from typing import Any


class FastSetError(Exception): ...


class RPCError(FastSetError):
    def __init__(self, code: int | None, message: str | None, response: Any | None = None) -> None:
        super().__init__(f"RPC error {code}: {message}")
        self.code = code
        self.response = response
