from __future__ import annotations

import time
from dataclasses import dataclass
from nacl.signing import SigningKey
from .constants import HRP, SET_TOKEN_ID
from .utils import bech32m as b32
from .utils import bcs as B

@dataclass(slots=True)
class TokenTransfer:
    token_id: bytes
    amount_hex: str
    user_data: bytes | None = None

@dataclass(slots=True)
class Transaction:
    sender_pubkey: bytes
    recipient_pubkey: bytes
    nonce: int
    timestamp_nanos: int
    claim: TokenTransfer

def bcs_serialize_transaction(tx: Transaction) -> bytes:
    sender = B.bytes32(tx.sender_pubkey)
    recipient_fastset = B.enum_bcs(0, B.bytes32(tx.recipient_pubkey))
    nonce = B.u64(tx.nonce)
    ts = B.u128(tx.timestamp_nanos)
    tt = B.concat(B.bytes32(tx.claim.token_id), B.u256_from_hex_le(tx.claim.amount_hex), B.option_bytes32(tx.claim.user_data))
    claim = B.enum_bcs(0, tt)
    return B.concat(sender, recipient_fastset, nonce, ts, claim)

@dataclass(slots=True)
class SignedTransaction:
    tx: Transaction
    signature: bytes

@dataclass(slots=True)
class TxCertificate:
    raw: dict

class FastSetTransactions:
    def __init__(self, client):
        self.client = client

    async def get_next_nonce(self, address_set: str | None = None) -> int:
        addr = address_set or self.client.account.address
        info = await self.client.wallet.get_account_info(addr)
        return int(info.get("next_nonce", 0))

    async def _submit_transaction(self, transaction: dict, signature: bytes) -> dict:
        return await self.client._rpc_call("set_proxy_submitTransaction", {"transaction": transaction, "signature": list(signature)})

    async def build_token_transfer(self, *, recipient_address_set: str, amount_hex: str, token_id: bytes | None = None, user_data: bytes | None = None, nonce: int | None = None, timestamp_nanos: int | None = None) -> Transaction:
        sender = self.client.account
        recipient_pub = b32.decode(recipient_address_set, HRP)
        if nonce is None:
            nonce = await self.get_next_nonce(sender.address)
        if timestamp_nanos is None:
            timestamp_nanos = int(time.time_ns())
        return Transaction(sender_pubkey=sender.public_key, recipient_pubkey=recipient_pub, nonce=int(nonce), timestamp_nanos=int(timestamp_nanos), claim=TokenTransfer(token_id=token_id or SET_TOKEN_ID, amount_hex=amount_hex, user_data=user_data))

    async def sign(self, tx: Transaction) -> SignedTransaction:
        sender = self.client.account
        bcs_bytes = bcs_serialize_transaction(tx)
        data = b"Transaction::" + bcs_bytes
        sig = SigningKey(sender.private_key).sign(data).signature
        return SignedTransaction(tx=tx, signature=sig)

    async def submit(self, signed: SignedTransaction) -> TxCertificate:
        tx = signed.tx
        tx_json = {"sender": tx.sender_pubkey, "recipient": {"FastSet": tx.recipient_pubkey}, "nonce": tx.nonce, "timestamp_nanos": str(tx.timestamp_nanos), "claim": {"TokenTransfer": {"token_id": tx.claim.token_id, "amount": tx.claim.amount_hex.lower().removeprefix("0x"), "user_data": tx.claim.user_data if tx.claim.user_data is not None else None}}}
        raw = await self._submit_transaction(tx_json, signed.signature)
        return TxCertificate(raw=raw)

    async def send_token_transfer(self, *, recipient_address_set: str, amount_hex: str, token_id: bytes | None = None, user_data: bytes | None = None, nonce: int | None = None, timestamp_nanos: int | None = None) -> TxCertificate:
        tx = await self.build_token_transfer(recipient_address_set=recipient_address_set, amount_hex=amount_hex, token_id=token_id, user_data=user_data, nonce=nonce, timestamp_nanos=timestamp_nanos)
        signed = await self.sign(tx)
        return await self.submit(signed)
