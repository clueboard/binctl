#!/usr/bin/env python3
"""manage.py: Server-side admin operations for binctl."""

import getpass
import os
import sys

if not os.environ.get('DATABASE_URL'):
    print('Error: DATABASE_URL environment variable is not set', file=sys.stderr)
    sys.exit(1)

from milc import cli  # noqa: E402

import db.direct as _db  # noqa: E402


@cli.entrypoint('manage: binctl server administration.')
def main(cli):
    """Top-level entrypoint. If no subcommand is given, show help."""
    cli.print_usage()


@cli.subcommand('Create a new user.')
def create_user(cli):
    username = input('Username: ').strip()
    if not username:
        cli.log.error('Username cannot be empty')
        raise SystemExit(1)
    password = getpass.getpass('Password: ')
    confirm = getpass.getpass('Confirm password: ')
    if password != confirm:
        cli.log.error('Passwords do not match')
        raise SystemExit(1)

    try:
        _db.create_user(username, password)
        cli.log.info(f"User '{username}' created.")
    except Exception as exc:
        cli.log.error('Error: %s', exc)
        raise SystemExit(1)


@cli.subcommand('List all users.')
def list_users(cli):
    rows = _db.fetch_all_users()
    if not rows:
        cli.log.info('No users.')
        return
    for row in rows:
        cli.log.info(f'[{row["id"]}] {row["username"]}  created={row["created_at"]}  last_login={row["last_login_at"]}')


@cli.argument('username', help='Username to look up')
@cli.subcommand('List tokens for a user.')
def list_tokens(cli):
    rows = _db.fetch_tokens_for_username(cli.args.username)
    if rows is None:
        cli.log.error("User '%s' not found.", cli.args.username)
        raise SystemExit(1)
    if not rows:
        cli.log.info(f"No tokens for '{cli.args.username}'.")
        return
    for row in rows:
        cli.log.info(f'[{row["id"]}] {row["token"]}  created={row["created_at"]}  last_used={row["last_used_at"]}  expires={row["expires_at"]}')


@cli.argument('username', help='Username to revoke tokens for')
@cli.subcommand('Revoke all tokens for a user.')
def revoke_tokens(cli):
    count = _db.revoke_tokens_for_username(cli.args.username)
    if count is None:
        cli.log.error("User '%s' not found.", cli.args.username)
        raise SystemExit(1)
    cli.log.info(f"Revoked {count} token(s) for '{cli.args.username}'.")


if __name__ == '__main__':
    cli()
