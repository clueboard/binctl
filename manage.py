#!/usr/bin/env python3
"""manage.py: Server-side admin operations for binctl."""

from __future__ import annotations

import argparse
import getpass
import os
import sys

if not os.environ.get('DATABASE_URL'):
    print('Error: DATABASE_URL environment variable is not set', file=sys.stderr)
    sys.exit(1)

from sqlalchemy import text  # noqa: E402

import db as _db  # noqa: E402
from auth import hash_password  # noqa: E402


def create_user() -> None:
    username = input('Username: ').strip()
    if not username:
        print('Username cannot be empty', file=sys.stderr)
        sys.exit(1)
    password = getpass.getpass('Password: ')
    confirm = getpass.getpass('Confirm password: ')
    if password != confirm:
        print('Passwords do not match', file=sys.stderr)
        sys.exit(1)

    pw_hash = hash_password(password)
    with _db.engine.connect() as conn:
        try:
            conn.execute(
                text('INSERT INTO users (username, password_hash) VALUES (:u, :h)'),
                {'u': username, 'h': pw_hash},
            )
            conn.commit()
            print(f"User '{username}' created.")
        except Exception as exc:
            print(f'Error: {exc}', file=sys.stderr)
            sys.exit(1)


def list_users() -> None:
    with _db.engine.connect() as conn:
        rows = conn.execute(
            text('SELECT id, username, created_at, last_login_at FROM users ORDER BY id')
        ).mappings().all()

    if not rows:
        print('No users.')
        return
    for row in rows:
        print(f"[{row['id']}] {row['username']}  created={row['created_at']}  last_login={row['last_login_at']}")


def revoke_tokens(username: str) -> None:
    with _db.engine.connect() as conn:
        user = conn.execute(
            text('SELECT id FROM users WHERE username = :u'),
            {'u': username},
        ).mappings().first()
        if user is None:
            print(f"User '{username}' not found.", file=sys.stderr)
            sys.exit(1)
        result = conn.execute(
            text('DELETE FROM tokens WHERE user_id = :uid'),
            {'uid': user['id']},
        )
        conn.commit()
        print(f"Revoked {result.rowcount} token(s) for '{username}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description='binctl server management')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('create-user', help='Create a new user')
    sub.add_parser('list-users', help='List all users')
    revoke = sub.add_parser('revoke-tokens', help='Revoke all tokens for a user')
    revoke.add_argument('username')

    args = parser.parse_args()
    if args.command == 'create-user':
        create_user()
    elif args.command == 'list-users':
        list_users()
    elif args.command == 'revoke-tokens':
        revoke_tokens(args.username)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
