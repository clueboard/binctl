import connexion
from connexion.exceptions import Unauthorized

from db.direct import fetch_token_and_touch
from db.flask import create_user_session, revoke_token, verify_password
from web import error


def lookup_token(token: str, required_scopes: object = None) -> dict:  # noqa: ARG001
    """Connexion x-bearerInfoFunc security handler."""
    row = fetch_token_and_touch(token)
    if row is None:
        raise Unauthorized('Invalid or expired token')
    return {
        'sub': row['username'],
        'user_id': row['user_id'],
        'token_id': row['token_id'],
    }


def login(body: dict):
    username = body.get('username', '').strip()
    password = body.get('password', '')
    row = verify_password(username, password)
    if row is None:
        return error(401, 'Invalid credentials')
    token = create_user_session(row['id'])
    return {'token': token}, 200


def logout():
    token_info = connexion.context.context['token_info']
    revoke_token(token_info['token_id'])
    return '', 204
