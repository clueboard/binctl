_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
_BASE = 62
_CHAR_TO_INT = {c: i for i, c in enumerate(_ALPHABET)}


def encode(n: int) -> str:
    if n == 0:
        return _ALPHABET[0]
    digits = []
    while n:
        digits.append(_ALPHABET[n % _BASE])
        n //= _BASE
    return ''.join(reversed(digits))


def decode(s: str) -> int:
    if not s:
        raise ValueError('empty string')
    result = 0
    for c in s:
        if c not in _CHAR_TO_INT:
            raise ValueError(f'invalid base62 character: {c!r}')
        result = result * _BASE + _CHAR_TO_INT[c]
    return result


def decode_id(s: str) -> int:
    """Decode a canonical base62 signed-BIGINT identifier."""
    value = decode(s)
    if value < 1 or value > (1 << 63) - 1 or encode(value) != s:
        raise ValueError('identifier must be canonical base62 in the signed 64-bit range')
    return value
