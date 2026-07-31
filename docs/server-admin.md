# Server administration

Server-side user and token management is handled with `manage.py`, which loads `.env`
automatically (see [Configuration](configuration.md)).

| Command | Description |
|---|---|
| `python manage.py init-db` | Initialize the database schema |
| `python manage.py create-user <username> --password <p>` | Create a user with a password |
| `python manage.py create-user <username> --token` | Create a passwordless user and emit a non-expiring token |
| `python manage.py set-password <username>` | Interactively set a new password for a user |
| `python manage.py list-users` | List users |
| `python manage.py list-tokens <username>` | List tokens for a user |
| `python manage.py revoke-tokens <username>` | Revoke all tokens for a user |

## Choosing an auth method

- **Tokens** (`--token`) are recommended for scripts and automation. Tokens created this way do
  not expire by default.
- **Passwords** are intended for interactive/browser use. Sessions created via the login API
  expire after `SESSION_LIFETIME_DAYS` (default 30 days).

See [Security](security.md) for token handling guidance and password requirements.

## Running the server

```bash
uvicorn web:create_app --factory
```

This binds to `http://localhost:5000` by default. Pass `--base-url http://localhost:<port>` to
`binctl` if you changed the port, or put a reverse proxy in front for TLS termination — see
[Security](security.md).
