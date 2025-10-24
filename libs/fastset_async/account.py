from __future__ import annotations

from dataclasses import dataclass
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError
from .constants import HRP
from .utils import bech32m as b32

@dataclass(slots=True)
class Account:
    private_key: bytes
    public_key: bytes
    address: str

    @classmethod
    async def from_private_hex(cls, private_key: str) -> "Account":
        priv = bytes.fromhex(private_key.removeprefix("0x"))
        if len(priv) != 32:
            raise ValueError("expected 32-byte ed25519 seed hex")
        pub = SigningKey(priv).verify_key.encode()
        addr = b32.encode(HRP, pub)
        return cls(private_key=priv, public_key=pub, address=addr)

    def private_key_hex(self) -> str:
        return self.private_key.hex()

    def public_key_hex(self) -> str:
        return self.public_key.hex()

    async def sign_message(self, message: bytes | str, *, hex_message: bool = False) -> bytes:
        data = bytes.fromhex(message) if (isinstance(message, str) and hex_message) else (message.encode("utf-8") if isinstance(message, str) else message)
        return SigningKey(self.private_key).sign(data).signature

    async def verify_signature(self, message: bytes | str, signature: bytes | str, *, hex_message: bool = False) -> bool:
        data = bytes.fromhex(message) if (isinstance(message, str) and hex_message) else (message.encode("utf-8") if isinstance(message, str) else message)
        sig = bytes.fromhex(signature) if isinstance(signature, str) else signature
        try:
            VerifyKey(self.public_key).verify(data, sig)
            return True
        except BadSignatureError:
            return False
