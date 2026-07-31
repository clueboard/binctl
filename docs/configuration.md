# Configuration

Configuration is provided via environment variables. Both the server and `manage.py` load a
`.env` file in the project root automatically — no manual `export` needed (though you can still
export variables directly if you prefer).

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
| `SESSION_LIFETIME_DAYS` | `30` | Expiry, in days, for tokens created via the login API (web/browser sessions). Tokens created with `python manage.py create-user --token` do not expire by default. |

## Orphan handling

| Variable | Default | Description |
|---|---|---|
| `ORPHAN_LOCATION` | unset | Container label used to receive direct children when their parent container is deleted. If no matching container exists outside the deleted subtree, one is created automatically as a new root container. |

See [Concepts](concepts.md#edges) for more on how deletion and reassignment work.
