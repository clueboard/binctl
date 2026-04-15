import hashlib
import hmac
import math
import os
import secrets

_TOKEN_BYTES = 32
TOKEN_LENGTH = math.ceil(_TOKEN_BYTES * 4 / 3)  # base64url length without padding

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _SCRYPT_DKLEN = 2**18, 8, 1, 32
_SCRYPT_MAXMEM = 512 * 1024 * 1024  # 512 MB; 2× the 256 MB required for N=2**18


def hash_password(password: str) -> str:
    salt = os.urandom(32)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN, maxmem=_SCRYPT_MAXMEM)
    return f'scrypt:{_SCRYPT_N}:{_SCRYPT_R}:{_SCRYPT_P}:{_SCRYPT_DKLEN}:{salt.hex()}:{digest.hex()}'


def verify_password_hash(password: str, stored: str) -> bool:
    """Raises ValueError or binascii.Error on malformed or tampered hash; caller handles exceptions."""
    prefix, n, r, p, dklen, salt_hex, digest_hex = stored.split(':', 6)
    if prefix != 'scrypt':
        raise ValueError(f'Unsupported hash type: {prefix!r}')
    n, r, p, dklen = int(n), int(r), int(p), int(dklen)
    if (n, r, p, dklen) != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _SCRYPT_DKLEN):
        raise ValueError(f'Unexpected scrypt parameters: n={n} r={r} p={p} dklen={dklen}')
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=n, r=r, p=p, dklen=dklen, maxmem=_SCRYPT_MAXMEM)
    return hmac.compare_digest(digest.hex(), digest_hex)


def generate_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a raw API token."""
    return hashlib.sha256(token.encode()).hexdigest()


def mask_token(suffix: str, total_length: int = TOKEN_LENGTH) -> str:
    """Return a masked token string, e.g. '************abcd'."""
    if len(suffix) > 4:
        suffix = suffix[-4:]
    return '*' * (total_length - len(suffix)) + suffix
