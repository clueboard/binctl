# Server administration

Server-side user and token management is handled with `binctl-manage`, which loads `.env`
automatically (see [Configuration](configuration.md)).

| Command | Description |
|---|---|
| `binctl-manage init-db` | Initialize the database schema |
| `binctl-manage create-user <username> --password <p>` | Create a user with a password |
| `binctl-manage create-user <username> --token` | Create a passwordless user and emit a non-expiring token |
| `binctl-manage set-password <username>` | Interactively set a new password for a user |
| `binctl-manage list-users` | List users |
| `binctl-manage list-tokens <username>` | List tokens for a user |
| `binctl-manage revoke-tokens <username>` | Revoke all tokens for a user |

## Choosing an auth method

- **Tokens** (`--token`) are recommended for scripts and automation. Tokens created this way do
  not expire by default.
- **Passwords** are intended for interactive/browser use. Sessions created via the login API
  expire after `SESSION_LIFETIME_DAYS` (default 30 days).

See [Security](security.md) for token handling guidance and password requirements.

## Running the server

```bash
uvicorn binctl_server.web:create_app --factory
```

This binds to `http://localhost:5000` by default. Pass `--base-url http://localhost:<port>` to
`binctl` if you changed the port, or put a reverse proxy in front for TLS termination — see
[Security](security.md).

## Running as a systemd service

A ready-to-use unit file is shipped as part of `binctl-server`:

- **Installed from PyPI** (`pip install binctl-server`): it's placed at
  `<venv>/share/binctl/systemd/binctl-server.service` inside whatever virtual environment you
  installed into, e.g. `/srv/binctl/.venv/share/binctl/systemd/binctl-server.service`.
- **From a git checkout**: it's at
  [`systemd/binctl-server.service`](https://github.com/clueboard/binctl/blob/main/systemd/binctl-server.service)
  in the repo root (also included in the sdist).

1. Set up the project on the server, e.g. under `/srv/binctl` — follow
   [Installation](installation.md) to create the virtual environment, install `binctl-server`
   (plus any DB driver extra you need), and create `.env` with `DATABASE_URL` and any other
   settings from [Configuration](configuration.md). Then initialize the database and create a
   user with `binctl-manage init-db` and `binctl-manage create-user ...`.

2. Create a dedicated system user/group to run the service, and make sure it owns the install
   directory:

   ```bash
   sudo useradd --system --home-dir /srv/binctl --shell /usr/sbin/nologin binctl
   sudo chown -R binctl:binctl /srv/binctl
   ```

3. Copy the unit file into place and adjust paths/host/port if your install directory differs
   from `/srv/binctl`:

   ```bash
   sudo cp /srv/binctl/.venv/share/binctl/systemd/binctl-server.service /etc/systemd/system/binctl-server.service
   sudo $EDITOR /etc/systemd/system/binctl-server.service
   ```

   The unit's `Environment=` lines (`DATABASE_URL`, `CORS_ORIGINS`, `CORS_MAX_AGE`,
   `SESSION_LIFETIME_DAYS`, `ORPHAN_LOCATION`) are all commented out by default, since binctl
   already loads `/srv/binctl/.env` on its own. Uncomment them (or `EnvironmentFile=`) only if
   you'd rather manage configuration through systemd instead of, or in addition to, `.env`.

4. Reload systemd, then enable and start the service:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now binctl-server
   ```

5. Check status and logs:

   ```bash
   sudo systemctl status binctl-server
   sudo journalctl -u binctl-server -f
   ```
