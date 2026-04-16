# binctl

`binctl` is a tiny graph-based inventory system for people with too many bins, boxes, and shelves.

Instead of thinking in terms of "SKUs" and "stock levels", `binctl` models your world as:

- **nodes** - items, bins, shelves, rooms, etc.
- **edges** - "this thing lives inside that thing".

It's backed by a Flask API with a CLI frontend.

## Setup

1. Copy `.env.example` and fill in your database URL:
   ```
   cp .env.example .env
   ```
2. Install the optional driver for your database (SQLite needs none — it's built into Python):
   - **MySQL:** `pip install 'binctl[mysql]'`
   - **PostgreSQL:** `pip install 'binctl[postgresql]'`
3. Set `DATABASE_URL` and start the server:
   ```
   export DATABASE_URL=sqlite:///binctl.db
   uvicorn web:create_app --factory
   ```
   Other supported URL formats:
   - MySQL: `mysql+pymysql://user:password@localhost/binctl`
   - PostgreSQL: `postgresql+psycopg2://user:password@localhost/binctl`
4. Create a user and token:
   ```
   python manage.py create-user --username alice
   ```
   Then pass `--token <token>` (or `--username`/`--password`) to `binctl` commands.

## CLI

- `binctl node list|get|create|update` - manage nodes
- `binctl tag list|get|create|update`  - manage tags

> **Note:** The API does not yet support DELETE. Nodes and tags can be created
> and updated but not removed via the API.

`manage.py` subcommands (server-side user/token management):

- `python manage.py create-user` - create a user
- `python manage.py list-users` - list users
- `python manage.py list-tokens` - list tokens for a user
- `python manage.py revoke-tokens` - revoke all tokens for a user

## Security

`binctl` is not designed to be exposed to the internet. It is intended for use on trusted local or private networks. Security bugs will be fixed when found, but the threat model assumes a trusted network environment.

**If you must expose the server to untrusted networks**, place a reverse proxy such as nginx or Caddy in front of it to handle:

- **SSL/TLS termination** — the Flask/uvicorn server does not handle TLS on its own.
- **Rate limiting on `POST /v1/auth/login`** — scrypt makes each login attempt slow, but a determined attacker can still brute-force credentials over time without a request rate limit.

**Token security** — tokens created via the login API (web/browser sessions) expire after 30 days by default; set `SESSION_LIFETIME_DAYS` to override. Tokens created via `python manage.py create-user` do not expire by default. All tokens should be treated with the same secrecy as a password: store them safely, do not share them, and revoke compromised tokens promptly with `python manage.py revoke-tokens`.

**Password policy** — the application does not enforce any minimum password strength. Choose a strong password of at least 16 characters using a mix of uppercase letters, lowercase letters, digits, and symbols.

## Tests / CI

The following must pass before merging:

```
uv run pytest
uv run ruff check
uv run ty check
```

---

## Concepts

### Nodes

Everything is a node:

- items (tools, parts, one-off widgets)
- containers (bins, boxes, drawers)
- higher-level containers (shelves, rooms, buildings)

Nodes live in the `nodes` table:

- `id` - BIGINT primary key
- `label` - human-readable name
- `description` - optional free text
- `is_container` - `TRUE` if this node can contain children

### Edges

Containment is modeled via the `edges` table:

- `parent_id` → `child_id`
- each child has **at most one parent** (enforced by a UNIQUE constraint)
- self-loops are rejected (`parent_id <> child_id`)

This gives you a **forest of trees**:

- top-level nodes (rooms, "unplaced items") have no parent
- containers and items have exactly one parent
- containers can have many children

### Tags

Tags are stored in `tags` + `tag_node` for future filtering and categorization.

Tags are exposed via `binctl tag list|get|create|update`.
