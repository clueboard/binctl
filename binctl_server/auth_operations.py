"""auth_operations: API handlers for various authentication related endpoints."""

import connexion
from connexion.exceptions import Unauthorized

from .db.auth import fetch_token_and_touch as db_fetch_token_and_touch
from .db.flask import create_user_session, revoke_token, verify_password
from .web import error


def _fetch_token_and_touch(token: str) -> dict | None:
    """Fetch token+user row and update last_used_at.

    The SELECT and UPDATE are separate statements; last_used_at is a
    best-effort audit field and a missed update on crash is harmless.

    Opens its own connection — safe to call outside a Flask request context
    (e.g. from Connexion's ASGI security middleware).
    Returns None if the token does not exist or has expired.
    """
    return db_fetch_token_and_touch(token)


def lookup_token(token: str, required_scopes: object = None) -> dict:  # noqa: ARG001
    """Connexion x-bearerInfoFunc security handler."""
    row = _fetch_token_and_touch(token)
    if row is None:
        raise Unauthorized('Invalid or expired token')
    return {
        'sub': row['username'],
        'user_id': row['user_id'],
        'token_id': row['token_id'],
    }


def login(body: dict):
    """/v1/auth/login"""
    username = body.get('username', '').strip()
    password = body.get('password', '')
    row = verify_password(username, password)
    if row is None:
        return error(401, 'Invalid credentials')
    token = create_user_session(row['id'])
    return {'token': token}, 200


def logout():
    """/v1/auth/logout"""
    token_info = connexion.context.context['token_info']
    revoke_token(token_info['token_id'])
    return '', 204
