from __future__ import annotations

from typing import Any, Optional

from .constants import HRP
from .utils import bech32m as b32
from .utils.num import parse_int_maybe_hex, to_hex_noprefix


class Wallet:
    def __init__(self, client):
        self.client = client

    async def get_account_info(self, address_set: str | None = None, *, token_balances_filter: list[str] | None = None, certificate_by_nonce: int | None = None) -> dict:
        addr = address_set or self.client.account.address
        addr_bytes = b32.decode(addr, HRP)
        params: dict[str, Any] = {"address": list(addr_bytes)}
        if token_balances_filter is not None:
            params["token_balances_filter"] = token_balances_filter
        if certificate_by_nonce is not None:
            params["certificate_by_nonce"] = str(certificate_by_nonce)
        return await self.client._rpc_call("set_proxy_getAccountInfo", params)

    async def get_balance(self, address_set: str | None = None) -> int:
        info = await self.get_account_info(address_set)
        return parse_int_maybe_hex(info.get("balance", "0"))

    async def get_transfers(self, page: int = 1) -> dict:
        return await self.client._rpc_call("set_proxy_getTransfers", {"page": page})

    async def get_token_info(self, token_id_hex: str) -> dict:
        token_id_hex = token_id_hex.lower().removeprefix("0x")
        return await self.client._rpc_call("set_proxy_getTokenInfo", {"token_id": token_id_hex})

    async def faucet_drip(self, recipient_set: str, amount: int | str, token_id_hex: Optional[str] | None = None) -> dict:
        recipient = b32.decode(recipient_set, HRP)
        params = {"recipient": list(recipient), "amount": to_hex_noprefix(amount)}
        if token_id_hex:
            params["token_id"] = token_id_hex.lower().removeprefix("0x")
        return await self.client._rpc_call("set_proxy_faucetDrip", params)
