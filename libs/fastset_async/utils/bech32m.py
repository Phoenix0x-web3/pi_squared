from __future__ import annotations

_BECH32_ALPHABET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32M_CONST = 0x2BC830A3


def _polymod(vals: list[int]) -> int:
    chk = 1
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    for v in vals:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            if (b >> i) & 1:
                chk ^= GEN[i]
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _create_checksum(hrp: str, data: list[int]) -> list[int]:
    vals = _hrp_expand(hrp) + data
    polymod = _polymod(vals + [0, 0, 0, 0, 0, 0]) ^ _BECH32M_CONST
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _convertbits(data: bytes | list[int], from_bits: int, to_bits: int, *, pad: bool) -> bytes:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << to_bits) - 1
    for v in data:
        if isinstance(v, bytes):
            v = v[0]
        if v < 0 or v >> from_bits:
            raise ValueError("invalid data range")
        acc = (acc << from_bits) | v
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        raise ValueError("invalid padding")
    return bytes(ret)


def encode(hrp: str, payload32: bytes) -> str:
    words = _convertbits(payload32, 8, 5, pad=True)
    data = list(words)
    checksum = _create_checksum(hrp, data)
    return f"{hrp}1{''.join(_BECH32_ALPHABET[d] for d in data + checksum)}"


def decode(addr: str, expected_hrp: str) -> bytes:
    s = addr.lower()
    if "1" not in s:
        raise ValueError("invalid bech32m: no separator")
    hrp, data = s.split("1", 1)
    if hrp != expected_hrp:
        raise ValueError("unexpected HRP")
    vals = [_BECH32_ALPHABET.index(c) for c in data]
    if _polymod(_hrp_expand(hrp) + vals) != _BECH32M_CONST:
        raise ValueError("bech32m checksum failed")
    words = vals[:-6]
    return _convertbits(words, 5, 8, pad=False)
