from __future__ import annotations

import connexion

from auth import generate_token, verify_password
from db import create_user_session, fetch_user_by_username, revoke_token
from web import error

# Pre-computed bcrypt hash used when user is not found, so verify_password
# always does full key-stretching regardless of whether the username exists.
# Prevents timing attacks that distinguish "unknown user" from "wrong password".
_DUMMY_HASH = '$2b$12$.OT9HVdRiWO/c/eawiYjjOa1.ujHVTxLo3eKEU9gdhRAMwUSvO/ei'


def login(body: dict):
    username = body.get('username', '').strip()
    password = body.get('password', '')

    row = fetch_user_by_username(username)

    stored_hash = row['password_hash'] if row is not None else _DUMMY_HASH
    valid = verify_password(password, stored_hash)

    if not valid or row is None:
        return error(401, 'Invalid credentials')

    token = generate_token()
    create_user_session(row['id'], token)
    return {'token': token}, 200


def logout():
    token_info = connexion.context.context['token_info']
    revoke_token(token_info['token_id'])
    return '', 204
