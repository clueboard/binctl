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

import db.direct as _db  # noqa: E402
from auth import hash_password, mask_token  # noqa: E402


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

    try:
        _db.create_user(username, hash_password(password))
        print(f"User '{username}' created.")
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)


def list_users() -> None:
    rows = _db.fetch_all_users()
    if not rows:
        print('No users.')
        return
    for row in rows:
        print(f'[{row["id"]}] {row["username"]}  created={row["created_at"]}  last_login={row["last_login_at"]}')


def list_tokens(username: str) -> None:
    rows = _db.fetch_tokens_for_username(username)
    if rows is None:
        print(f"User '{username}' not found.", file=sys.stderr)
        sys.exit(1)
    if not rows:
        print(f"No tokens for '{username}'.")
        return
    for row in rows:
        print(
            f'[{row["id"]}] {mask_token(row["token_suffix"])}'
            f'  created={row["created_at"]}'
            f'  last_used={row["last_used_at"]}'
            f'  expires={row["expires_at"]}'
        )


def revoke_tokens(username: str) -> None:
    count = _db.revoke_tokens_for_username(username)
    if count is None:
        print(f"User '{username}' not found.", file=sys.stderr)
        sys.exit(1)
    print(f"Revoked {count} token(s) for '{username}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description='binctl server management')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('create-user', help='Create a new user')
    sub.add_parser('list-users', help='List all users')
    list_tok = sub.add_parser('list-tokens', help='List tokens for a user')
    list_tok.add_argument('username')
    revoke = sub.add_parser('revoke-tokens', help='Revoke all tokens for a user')
    revoke.add_argument('username')

    args = parser.parse_args()
    if args.command == 'create-user':
        create_user()
    elif args.command == 'list-users':
        list_users()
    elif args.command == 'list-tokens':
        list_tokens(args.username)
    elif args.command == 'revoke-tokens':
        revoke_tokens(args.username)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
