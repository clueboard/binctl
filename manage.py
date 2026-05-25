#!/usr/bin/env python3
"""manage.py: Server-side admin operations for binctl."""

import getpass
import os
import sys

from dotenv import find_dotenv, load_dotenv, set_key, unset_key

load_dotenv()

if not os.environ.get('DATABASE_URL'):
    print('Error: DATABASE_URL environment variable is not set', file=sys.stderr)
    sys.exit(1)

from pathlib import Path  # noqa: E402

import sqlalchemy  # noqa: E402
from milc import cli  # noqa: E402

import db  # noqa: E402
import db.direct  # noqa: E402


@cli.entrypoint('manage: binctl server administration.')
def main(cli):
    """Top-level entrypoint. If no subcommand is given, show help."""
    cli.print_usage()


@cli.subcommand('Initialize the database schema.')
def init_db(cli):
    schema = Path(__file__).parent / 'schemas' / 'v1.sql'
    sql = schema.read_text()
    with db.engine.connect() as conn:
        for stmt in sql.split(';'):
            stmt = stmt.strip()
            if stmt:
                conn.execute(sqlalchemy.text(stmt))
        conn.commit()
    cli.log.info('Database initialized.')


@cli.argument('--username', required=True, help='Username for the new account')
@cli.argument('--password', required=False, default=None, help='Password for the new account')
@cli.argument('--token', action='store_true', help='Generate a non-expiring token instead of setting a password')
@cli.subcommand('Create a new user.')
def create_user(cli):
    username = cli.args.username.strip()
    if not username:
        cli.log.error('Username cannot be empty')
        raise SystemExit(1)
    if cli.args.token and cli.args.password:
        cli.log.error('--token and --password are mutually exclusive')
        raise SystemExit(1)
    if cli.args.token:
        user_id = db.direct.create_user(username, password=None)
        token = db.direct.create_token(user_id)
        cli.log.info(f"User '{username}' created. Token: {token}")
    else:
        if not cli.args.password:
            cli.log.error('--password is required when --token is not set')
            raise SystemExit(1)
        if len(cli.args.password) < 4:
            cli.log.warning('Password is very short (fewer than 4 characters)')
        try:
            db.direct.create_user(username, password=cli.args.password)
        except Exception as exc:
            cli.log.error('Error: %s', exc)
            raise SystemExit(1)
        cli.log.info(f"User '{username}' created.")


@cli.argument('username', help='Username to update')
@cli.subcommand('Set password for a user.')
def set_password(cli):
    password = getpass.getpass('New password: ')
    if len(password) < 6:
        cli.log.error('Password must be at least 6 characters')
        raise SystemExit(1)
    confirm = getpass.getpass('Confirm password: ')
    if password != confirm:
        cli.log.error('Passwords do not match')
        raise SystemExit(1)
    if not db.direct.update_password(cli.args.username, password):
        cli.log.error("User '%s' not found.", cli.args.username)
        raise SystemExit(1)
    cli.log.info(f"Password updated for '{cli.args.username}'.")


@cli.subcommand('List all users.')
def list_users(cli):
    rows = db.direct.fetch_all_users()
    if not rows:
        cli.log.info('No users.')
        return
    for row in rows:
        cli.log.info(f'[{row["id"]}] {row["username"]}  created={row["created_at"]}  last_login={row["last_login_at"]}')


@cli.argument('username', help='Username to look up')
@cli.subcommand('List tokens for a user.')
def list_tokens(cli):
    rows = db.direct.fetch_tokens_for_username(cli.args.username)
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
    count = db.direct.revoke_tokens_for_username(cli.args.username)
    if count is None:
        cli.log.error("User '%s' not found.", cli.args.username)
        raise SystemExit(1)
    cli.log.info(f"Revoked {count} token(s) for '{cli.args.username}'.")


@cli.argument('label', help='Container label to receive children of deleted containers')
@cli.subcommand('Set the container label used when reassigning children from deleted containers.')
def set_orphan_reassign_container(cli):
    label = cli.args.label.strip()
    if not label:
        cli.log.error('Label cannot be empty')
        raise SystemExit(1)
    dotenv_path = find_dotenv(usecwd=True) or '.env'
    set_key(dotenv_path, 'ORPHAN_REASSIGN_CONTAINER', label)
    os.environ['ORPHAN_REASSIGN_CONTAINER'] = label
    cli.log.info(f'Orphan reassignment container label set to {label!r}.')


@cli.subcommand('Show the configured container label used for orphan reassignment.')
def show_orphan_reassign_container(cli):
    label = db.direct.get_orphan_reassign_container_label()
    if label is None:
        cli.log.info('No orphan reassignment container label is configured.')
        return
    cli.log.info(f'Orphan reassignment container label: {label}')


@cli.subcommand('Clear the configured container label used for orphan reassignment.')
def clear_orphan_reassign_container(cli):
    if db.direct.get_orphan_reassign_container_label() is None:
        cli.log.info('No orphan reassignment container label was configured.')
        return
    dotenv_path = find_dotenv(usecwd=True) or '.env'
    unset_key(dotenv_path, 'ORPHAN_REASSIGN_CONTAINER')
    os.environ.pop('ORPHAN_REASSIGN_CONTAINER', None)
    cli.log.info('Cleared orphan reassignment container label.')


if __name__ == '__main__':
    cli()
