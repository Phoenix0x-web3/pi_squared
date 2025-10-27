from __future__ import annotations

import os
from typing import Any

from nacl.signing import SigningKey

from .account import Account
from .constants import FASTSET_DEFAULT_RPC, FASTSET_TIMEOUT, HRP
from .exceptions import RPCError
from .rpc import RPC
from .utils import bech32m as b32
from .wallet import Wallet


def _jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (bytes, bytearray)):
        return list(obj)
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    return obj

class FastSetClient:
    base_headers = {"Content-Type": "application/json", "Accept": "application/json"}

    def __init__(self, private_key: str | None = None, rpc_url: str = FASTSET_DEFAULT_RPC, *, timeout: int = FASTSET_TIMEOUT, proxy: str | None = None):
        super().__init__()
        self.rpc_url = rpc_url
        self.timeout = timeout
        self.rpc = RPC(proxy=proxy, timeout=timeout, base_headers=self.base_headers)
        self._rid = 0
        self.account = self._build_account(private_key) if private_key else self._build_account(private_key=os.urandom(32).hex())
        from .transactions import FastSetTransactions
        self.wallet = Wallet(self)
        self.transactions = FastSetTransactions(self)

    def _build_account(self, private_key: str) -> Account:
        priv = bytes.fromhex(private_key.removeprefix("0x"))
        if len(priv) != 32:
            raise ValueError("expected 32-byte ed25519 seed hex")
        pub = SigningKey(priv).verify_key.encode()
        addr = b32.encode(HRP, pub)
        return Account(private_key=priv, public_key=pub, address=addr)

    def _next_id(self) -> int:
        self._rid += 1
        return self._rid

    async def _rpc_call(self, method: str, params: dict | None = None) -> Any:
        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": method, "params": _jsonable(params or {})}
        r = await self.rpc.post(self.rpc_url, json=payload)
        js = r.json()
        if js.get("error"):
            err = js["error"]
            raise RPCError(err.get("code"), err.get("message"), response=js)
        return js.get("result")
