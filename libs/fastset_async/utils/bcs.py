from __future__ import annotations


def u8(x: int) -> bytes:
    return int(x).to_bytes(1, "little", signed=False)


def u64(x: int) -> bytes:
    return int(x).to_bytes(8, "little", signed=False)


def u128(x: int) -> bytes:
    return int(x).to_bytes(16, "little", signed=False)


def u256_from_hex_le(hex_str: str) -> bytes:
    s = str(hex_str).lower().removeprefix("0x") or "0"
    val = int(s, 16)
    return val.to_bytes(32, "little", signed=False)


def bytes32(b: bytes) -> bytes:
    if len(b) != 32:
        raise ValueError("expected 32 bytes")
    return b


def option_bytes32(b: bytes | None) -> bytes:
    return u8(0) if b is None else (u8(1) + bytes32(b))


def enum_bcs(variant_index: int, payload: bytes) -> bytes:
    return u8(variant_index) + payload


def concat(*parts: bytes) -> bytes:
    return b"".join(parts)


def uleb128(x: int) -> bytes:
    x = int(x)
    out = bytearray()
    while True:
        b = x & 0x7F
        x >>= 7
        if x:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def bcs_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return uleb128(len(b)) + b


def vec(items: list[bytes]) -> bytes:
    return uleb128(len(items)) + b"".join(items)
