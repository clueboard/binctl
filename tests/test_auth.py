import pytest

from auth import _SCRYPT_DKLEN, _SCRYPT_N, _SCRYPT_P, _SCRYPT_R, hash_password, verify_password_hash, mask_token, TOKEN_LENGTH


def test_round_trip():
    h = hash_password('hunter2')
    assert verify_password_hash('hunter2', h) is True


def test_wrong_password():
    h = hash_password('hunter2')
    assert verify_password_hash('wrong', h) is False


def test_unique_salts():
    assert hash_password('x') != hash_password('x')


def test_wrong_prefix():
    h = hash_password('x').replace('scrypt:', 'argon2:', 1)
    with pytest.raises(ValueError, match='Unsupported hash type'):
        verify_password_hash('x', h)


def test_wrong_n():
    h = hash_password('x')
    tampered = h.replace(f'scrypt:{_SCRYPT_N}:', 'scrypt:1024:', 1)
    with pytest.raises(ValueError, match='Unexpected scrypt parameters'):
        verify_password_hash('x', tampered)


def test_wrong_dklen():
    h = hash_password('x')
    parts = h.split(':')
    parts[4] = str(_SCRYPT_DKLEN + 1)
    with pytest.raises(ValueError, match='Unexpected scrypt parameters'):
        verify_password_hash('x', ':'.join(parts))


def test_truncated_fields():
    h = ':'.join(hash_password('x').split(':')[:5])  # drop salt and digest
    with pytest.raises(ValueError):
        verify_password_hash('x', h)


def test_empty_string():
    with pytest.raises(ValueError):
        verify_password_hash('x', '')


def test_hash_format():
    h = hash_password('x')
    prefix, n, r, p, dklen, salt_hex, digest_hex = h.split(':')
    assert prefix == 'scrypt'
    assert int(n) == _SCRYPT_N
    assert int(r) == _SCRYPT_R
    assert int(p) == _SCRYPT_P
    assert int(dklen) == _SCRYPT_DKLEN
    assert len(bytes.fromhex(salt_hex)) == 32


def test_mask_token():
    assert mask_token('abcdefgh') == '*' * (TOKEN_LENGTH - 4) + 'efgh'
    assert mask_token('abcd') == '*' * (TOKEN_LENGTH - 4) + 'abcd'
    assert mask_token('') == '*' * TOKEN_LENGTH
    assert mask_token('abc') == '*' * (TOKEN_LENGTH - 3) + 'abc'
