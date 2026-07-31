# binctl

`binctl` is a tiny graph-based inventory system for people with too many bins, boxes, and shelves.

Instead of thinking in terms of "SKUs" and "stock levels", `binctl` models your world as:

- **nodes** - items, bins, shelves, rooms, etc.
- **edges** - "this thing lives inside that thing".

It's backed by a Flask API with a CLI frontend.

## Install from PyPI

```bash
pip install binctl-server
```

Install database drivers only when needed:

- **MySQL:** `pip install 'binctl-server[mysql]'`
- **PostgreSQL:** `pip install 'binctl-server[postgresql]'`

## Quickstart (SQLite, local dev)

The fastest path to a running system. Requires Python 3.11+. Run each block in your terminal:

```bash
# 1. Generate the ignored API client
./genclient.sh

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies — binctl-client is installed from PyPI
pip install -e .

# 4. Configure the database — copy .env.example and uncomment the SQLite line
cp .env.example .env
# In .env, uncomment: DATABASE_URL=sqlite:///binctl.db

# 5. Initialize the database
python manage.py init-db

# 6. Create a user and get a token
python manage.py create-user alice --token
# → prints something like: token: abc123...
export TOKEN=<paste token here>

# 7. Start the server (keep this terminal open, or run it in the background)
uvicorn web:create_app --factory

# 8. In another terminal (with .venv activated), verify it works
binctl --token $TOKEN node list
```

## Setup

1. Generate the API client, then create and activate a virtual environment and install dependencies:
   ```
   ./genclient.sh
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -e .
   ```
   `binctl-client` is installed from PyPI. `genclient.sh` uses `uvx` to generate a
   local client from `openapi.yaml` as an API-contract check; its `binctl-client/`
   output is ignored and must not be committed.

   If you need MySQL or PostgreSQL support, install the optional driver afterward:
   - **MySQL:** `pip install pymysql`  or  `pip install 'binctl-server[mysql]'`
   - **PostgreSQL:** `pip install psycopg2-binary`  or  `pip install 'binctl-server[postgresql]'`
   - **SQLite** — no extra driver needed, skip this step.

2. Copy `.env.example` and set your database URL:
   ```
   cp .env.example .env
   ```
   Supported URL formats:
   - SQLite: `sqlite:///binctl.db`
   - MySQL: `mysql+pymysql://user:password@localhost/binctl`
   - PostgreSQL: `postgresql+psycopg2://user:password@localhost/binctl`

   The server and `manage.py` load `.env` automatically — no manual `export` needed.

3. Initialize the database:
   ```
   python manage.py init-db
   ```

4. Start the server:
   ```
   uvicorn web:create_app --factory
   ```

5. Create a user:
   - With a non-expiring API token (recommended for scripts):
     ```
     python manage.py create-user alice --token
     ```
   - With a password (for browser/interactive use):
     ```
     python manage.py create-user alice --password <password>
     ```
   Then pass `--token <token>` (or `--username`/`--password`) to `binctl` commands.

## CLI

- `binctl node list|get|create|update|delete` - manage nodes
- `binctl tag list|get|create|update|delete`  - manage tags

Key flags for `binctl`:

| Flag | Description |
|---|---|
| `--base-url` | API server URL (default: `http://localhost:5000`) |
| `--token` | Bearer token (preferred) |
| `--username` / `--password` | Login-based auth |

`manage.py` subcommands (server-side user/token management):

- `python manage.py init-db` - initialize the database schema
- `python manage.py create-user <username> --password <p>` - create a user with a password
- `python manage.py create-user <username> --token` - create a passwordless user and emit a non-expiring token
- `python manage.py set-password <username>` - interactively set a new password for a user
- `python manage.py list-users` - list users
- `python manage.py list-tokens <username>` - list tokens for a user
- `python manage.py revoke-tokens <username>` - revoke all tokens for a user

## Example: Building an inventory

This walks through creating a hierarchy (room → shelf → item), listing it, and moving a node.

Node IDs are opaque strings (e.g. `wGIDjZ0AAC`), not sequential integers. Copy them from the
output of each command — do not guess or construct them by hand.

```bash
export TOKEN=<your token>

# Create a room (a container)
binctl --token $TOKEN node create --label "Garage" --is-container
# → {"id": "wGIDjZ0AAC", "label": "Garage", "is_container": true, ...}

# Create a shelf inside the room — use the id from the previous output
binctl --token $TOKEN node create --label "Shelf A" --is-container --parent-id wGIDjZ0AAC
# → {"id": "xK3mPq1BBD", "label": "Shelf A", ...}

# Add an item to the shelf
binctl --token $TOKEN node create --label "Power drill" --parent-id xK3mPq1BBD
# → {"id": "yR7nTs2CCE", "label": "Power drill", ...}

# List everything
binctl --token $TOKEN node list

# Move the drill to a different shelf (use that shelf's id from its create output)
binctl --token $TOKEN node update --node-id yR7nTs2CCE --parent-id <other-shelf-id>

# Detach the drill entirely (no parent, becomes a root node)
binctl --token $TOKEN node update --node-id yR7nTs2CCE --no-parent
```

## Running as a service

A systemd unit file is shipped at [`systemd/binctl-server.service`](systemd/binctl-server.service)
for running the server persistently on a Linux host. Copy it to `/etc/systemd/system/`, adjust the
paths/user, then `systemctl daemon-reload && systemctl enable --now binctl-server`. See
[Server administration](docs/server-admin.md#running-as-a-systemd-service) for the full walkthrough.

## Security

`binctl` is not designed to be exposed to the internet. It is intended for use on trusted local or private networks. Security bugs will be fixed when found, but the threat model assumes a trusted network environment.

**If you must expose the server to untrusted networks**, place a reverse proxy such as nginx or Caddy in front of it to handle:

- **SSL/TLS termination** — the Flask/uvicorn server does not handle TLS on its own.
- **Rate limiting on `POST /v1/auth/login`** — scrypt makes each login attempt slow, but a determined attacker can still brute-force credentials over time without a request rate limit.

**Token security** — tokens created via the login API (web/browser sessions) expire after 30 days by default; set `SESSION_LIFETIME_DAYS` to override. Tokens created via `python manage.py create-user` do not expire by default. All tokens should be treated with the same secrecy as a password: store them safely, do not share them, and revoke compromised tokens promptly with `python manage.py revoke-tokens`.

**Password policy** — `set-password` enforces a minimum of 6 characters. No other complexity requirements are enforced by the application. Choose a strong password of at least 16 characters using a mix of uppercase letters, lowercase letters, digits, and symbols.

## Development (uv)

Contributors can use [uv](https://docs.astral.sh/uv/) for a faster workflow. Generate the
ignored local client first, then install the published `binctl-client` package and other
development dependencies.

```bash
# Install uv (skip if already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Generate the client from the API contract
./genclient.sh

# Install all dependencies including dev tools
uv sync

# Run checks
uv run pytest
uv run ruff check
uv run ty check
```

## Tests / CI

The following must pass before merging (run with the venv activated):

```
pytest
ruff check
ty check
```

## Publishing releases

In GitHub Actions, run the `Publish to PyPI` workflow and select the `patch`,
`minor`, or `major` version increment. The workflow runs from `main`, uses
`uv version --bump` to update `pyproject.toml` and `uv.lock`, commits the new
version, creates and pushes its matching `v<version>` tag, and publishes that
version to PyPI.

Before the first release, configure PyPI Trusted Publishing for
`clueboard/binctl` with workflow filename `publish.yml` and environment name
`pypi`. The workflow uses GitHub Actions OIDC, so it does not require a PyPI
API token or repository secret.

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

When you delete a container, any direct children can be reassigned by setting `ORPHAN_LOCATION` in your `.env`. The server looks up a container by that label at delete time, and if none exists outside the deleted subtree it creates a new root container with that label automatically.

### Tags

Tags are stored in `tags` + `tag_node` for future filtering and categorization.

Tags are exposed via `binctl tag list|get|create|update`.

## Troubleshooting

**`ModuleNotFoundError: No module named 'binctl_client'`**
Reinstall the project dependencies with `pip install -e .` or `uv sync`.

**`Connection refused` / `Failed to connect` when running `binctl` commands**
The server is not running. Start it with `uvicorn web:create_app --factory` (binds to
`http://localhost:5000` by default). If you changed the port, pass `--base-url http://localhost:<port>`
to `binctl`.

**`401 Unauthorized`**
Token is missing or wrong. Re-create one with `python manage.py create-user alice --token`,
or list existing tokens with `python manage.py list-tokens alice`.

**`DATABASE_URL not set` or database errors on startup**
Export the variable before running server or manage commands:
```
export DATABASE_URL=sqlite:///binctl.db
```
Or add it to your `.env` file (copied from `.env.example`).
