from __future__ import annotations

import connexion
from sqlalchemy import text

from auth import create_token, verify_password
from db import get_db, transactional
from web import error

# Dummy hash used for constant-time comparison when user is not found,
# preventing timing attacks that distinguish "no such user" from "wrong password".
_DUMMY_HASH = '$2b$12$invalidhashfortimingprevention0000000000000000000000000'


def login(body: dict):
    username = body.get('username', '').strip()
    password = body.get('password', '')

    db = get_db()
    row = db.execute(
        text('SELECT id, password_hash FROM users WHERE username = :u'),
        {'u': username},
    ).mappings().first()

    stored_hash = row['password_hash'] if row is not None else _DUMMY_HASH
    valid = verify_password(password, stored_hash)

    if not valid or row is None:
        return error(401, 'Invalid credentials')

    with transactional() as db:
        db.execute(
            text('UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = :id'),
            {'id': row['id']},
        )

    token = create_token(row['id'])
    return {'token': token}, 200


def logout():
    token_info = connexion.context.context['token_info']
    token_id = token_info['token_id']

    with transactional() as db:
        db.execute(
            text('DELETE FROM tokens WHERE id = :id'),
            {'id': token_id},
        )

    return '', 204
