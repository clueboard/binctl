# Configuration

The server reads system-wide defaults from `/etc/binctl.conf`. `binctl-manage` and `binctl` then
read the platform-specific user configuration file, whose matching settings override system
settings. For either CLI, passing `--config-file <path>` bypasses both defaults and reads only that
file.

The server and `binctl-manage` also load a `.env` file in the project root automatically. Exported
environment variables and `.env` settings override file-based server settings.

Configuration files use INI syntax. For example:

```ini
[general]
database_url = sqlite:////var/lib/binctl/binctl.db
cors_origins = https://inventory.example.com
base_url = https://inventory.example.com
token = your-client-token
```

Copy the example file to get started:

```bash
cp .env.example .env
```

## Database URL

Exactly one `DATABASE_URL` must be set:

| Backend | URL format |
|---|---|
| SQLite | `sqlite:///binctl.db` |
| MySQL | `mysql+pymysql://user:password@localhost/binctl` |
| PostgreSQL | `postgresql+psycopg2://user:password@localhost/binctl` |

SQLite needs no extra driver. MySQL and PostgreSQL need their optional driver installed — see
[Installation](installation.md).

## CORS

| Variable | Default | Description |
|---|---|---|
| `CORS_ORIGINS` | unset | Comma-separated list of allowed origins. Required for browser-based clients. |
| `CORS_MAX_AGE` | `600` | Preflight cache duration, in seconds. |

## Sessions and tokens

| Variable | Default | Description |
|---|---|---|
| `SESSION_LIFETIME_DAYS` | `30` | Expiry, in days, for tokens created via the login API (web/browser sessions). Tokens created with `binctl-manage create-user --token` do not expire by default. |

## Orphan handling

| Variable | Default | Description |
|---|---|---|
| `ORPHAN_LOCATION` | unset | Container label used to receive direct children when their parent container is deleted. If no matching container exists outside the deleted subtree, one is created automatically as a new root container. |

See [Concepts](concepts.md#edges) for more on how deletion and reassignment work.
