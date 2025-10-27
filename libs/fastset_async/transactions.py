from __future__ import annotations

import time
from dataclasses import dataclass

from nacl.signing import SigningKey

from .constants import HRP, SET_TOKEN_ID
from .utils import bcs as B
from .utils import bech32m as b32
from .utils.num import to_hex_noprefix


@dataclass(slots=True)
class TokenTransfer:
    token_id: bytes
    amount_hex: str
    user_data: bytes | None = None


@dataclass(slots=True)
class TokenCreation:
    token_name: str
    decimals: int
    initial_amount_hex: str
    mints: list[bytes]
    user_data: bytes | None = None


@dataclass(slots=True)
class Transaction:
    sender_pubkey: bytes
    recipient_pubkey: bytes
    nonce: int
    timestamp_nanos: int
    claim: TokenTransfer | TokenCreation


def bcs_serialize_token_transfer(claim: TokenTransfer) -> bytes:
    return B.concat(
        B.bytes32(claim.token_id),
        B.u256_from_hex_le(claim.amount_hex),
        B.option_bytes32(claim.user_data),
    )


def bcs_serialize_token_creation(claim: TokenCreation) -> bytes:
    return B.concat(
        B.bcs_str(claim.token_name),
        B.u8(claim.decimals),
        B.u256_from_hex_le(claim.initial_amount_hex),
        B.vec([B.bytes32(pk) for pk in claim.mints]),
        B.option_bytes32(claim.user_data),
    )


def bcs_serialize_transaction(tx: Transaction) -> bytes:
    sender = B.bytes32(tx.sender_pubkey)
    recipient_fastset = B.enum_bcs(0, B.bytes32(tx.recipient_pubkey))
    nonce = B.u64(tx.nonce)
    ts = B.u128(tx.timestamp_nanos)
    if isinstance(tx.claim, TokenTransfer):
        claim = B.enum_bcs(0, bcs_serialize_token_transfer(tx.claim))
    else:
        claim = B.enum_bcs(1, bcs_serialize_token_creation(tx.claim))
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

    async def _submit_transaction(self, transaction: dict, signature_obj: dict) -> dict:
        return await self.client._rpc_call(
            "set_proxy_submitTransaction",
            {"transaction": transaction, "signature": signature_obj},
        )

    async def build_token_transfer(
        self,
        *,
        recipient_address_set: str,
        amount_hex: str,
        token_id: bytes | None = None,
        user_data: bytes | None = None,
        nonce: int | None = None,
        timestamp_nanos: int | None = None,
    ) -> Transaction:
        sender = self.client.account
        recipient_pub = b32.decode(recipient_address_set, HRP)
        if nonce is None:
            nonce = await self.get_next_nonce(sender.address)
        if timestamp_nanos is None:
            timestamp_nanos = int(time.time_ns())
        return Transaction(
            sender_pubkey=sender.public_key,
            recipient_pubkey=recipient_pub,
            nonce=int(nonce),
            timestamp_nanos=int(timestamp_nanos),
            claim=TokenTransfer(
                token_id=token_id or SET_TOKEN_ID,
                amount_hex=amount_hex,
                user_data=user_data,
            ),
        )

    async def build_token_creation(
        self,
        *,
        token_name: str,
        decimals: int,
        initial_amount: int | str,
        mints_set_addresses: list[str] | None = None,
        user_data: bytes | None = None,
        nonce: int | None = None,
        timestamp_nanos: int | None = None,
    ) -> Transaction:
        sender = self.client.account
        recipient_pub = sender.public_key
        if nonce is None:
            nonce = await self.get_next_nonce(self.client.account.address)
        if timestamp_nanos is None:
            timestamp_nanos = int(time.time_ns())
        mints = []
        if mints_set_addresses:
            for addr in mints_set_addresses:
                mints.append(b32.decode(addr, HRP))
        return Transaction(
            sender_pubkey=sender.public_key,
            recipient_pubkey=recipient_pub,
            nonce=int(nonce),
            timestamp_nanos=int(timestamp_nanos),
            claim=TokenCreation(
                token_name=token_name,
                decimals=int(decimals),
                initial_amount_hex=to_hex_noprefix(initial_amount),
                mints=mints,
                user_data=user_data,
            ),
        )

    async def sign(self, tx: Transaction) -> SignedTransaction:
        bcs_bytes = bcs_serialize_transaction(tx)
        data = b"Transaction::" + bcs_bytes
        sig = SigningKey(self.client.account.private_key).sign(data).signature
        return SignedTransaction(tx=tx, signature=sig)

    async def submit(self, signed: SignedTransaction) -> TxCertificate:
        tx = signed.tx
        if isinstance(tx.claim, TokenTransfer):
            claim_obj = {
                "token_id": list(tx.claim.token_id),
                "amount": tx.claim.amount_hex.lower().removeprefix("0x"),
                "user_data": (list(tx.claim.user_data) if tx.claim.user_data is not None else None),
            }
            claim = {"TokenTransfer": claim_obj}
        else:
            claim_obj = {
                "token_name": tx.claim.token_name,
                "decimals": int(tx.claim.decimals),
                "initial_amount": tx.claim.initial_amount_hex.lower().removeprefix("0x"),
                "mints": [list(pk) for pk in tx.claim.mints],
                "user_data": (list(tx.claim.user_data) if tx.claim.user_data is not None else None),
            }
            claim = {"TokenCreation": claim_obj}
        tx_json = {
            "sender": list(tx.sender_pubkey),
            "recipient": {"FastSet": list(tx.recipient_pubkey)},
            "nonce": tx.nonce,
            "timestamp_nanos": tx.timestamp_nanos,
            "claim": claim,
        }
        sig_obj = {"Signature": list(signed.signature)}
        raw = await self._submit_transaction(tx_json, sig_obj)
        return TxCertificate(raw=raw)

    async def send_token_transfer(
        self,
        *,
        recipient_address_set: str,
        amount: int | str,
        token_id: bytes | None = None,
        user_data: bytes | None = None,
        nonce: int | None = None,
        timestamp_nanos: int | None = None,
    ) -> TxCertificate:
        amount_hex = to_hex_noprefix(amount)
        tx = await self.build_token_transfer(
            recipient_address_set=recipient_address_set,
            amount_hex=amount_hex,
            token_id=token_id,
            user_data=user_data,
            nonce=nonce,
            timestamp_nanos=timestamp_nanos,
        )
        signed = await self.sign(tx)
        return await self.submit(signed)

    async def create_token(
        self,
        *,
        token_name: str,
        decimals: int,
        initial_amount: int | str,
        mints_set_addresses: list[str] | None = None,
        user_data: bytes | None = None,
        nonce: int | None = None,
        timestamp_nanos: int | None = None,
    ) -> TxCertificate:
        tx = await self.build_token_creation(
            token_name=token_name,
            decimals=decimals,
            initial_amount=initial_amount,
            mints_set_addresses=mints_set_addresses,
            user_data=user_data,
            nonce=nonce,
            timestamp_nanos=timestamp_nanos,
        )
        signed = await self.sign(tx)
        return await self.submit(signed)
