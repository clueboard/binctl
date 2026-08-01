# Installation

## From PyPI

```bash
pip install binctl-server
```

Install database drivers only when needed:

- **MySQL:** `pip install 'binctl-server[mysql]'`
- **PostgreSQL:** `pip install 'binctl-server[postgresql]'`

## From source

1. Generate the API client, then create and activate a virtual environment and install
   dependencies:

   ```bash
   ./genclient.sh
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -e .
   ```

   `binctl-client` is installed from PyPI. `genclient.sh` uses `uvx` to generate a local client
   from `binctl_server/openapi.yaml` as an API-contract check; its `binctl-client/` output is
   ignored and must not be committed.

   If you need MySQL or PostgreSQL support, install the optional driver afterward:

   - **MySQL:** `pip install pymysql` or `pip install 'binctl-server[mysql]'`
   - **PostgreSQL:** `pip install psycopg2-binary` or `pip install 'binctl-server[postgresql]'`
   - **SQLite** — no extra driver needed, skip this step.

2. Copy `.env.example` and set your database URL. See [Configuration](configuration.md) for the
   full list of supported URL formats and options.

   ```bash
   cp .env.example .env
   ```

3. Initialize the database:

   ```bash
   binctl-manage init-db
   ```

4. Start the server:

   ```bash
   uvicorn binctl_server.web:create_app --factory
   ```

5. Create a user:

   - With a non-expiring API token (recommended for scripts):

     ```bash
     binctl-manage create-user alice --token
     ```

   - With a password (for browser/interactive use):

     ```bash
     binctl-manage create-user alice --password <password>
     ```

   Then pass `--token <token>` (or `--username`/`--password`) to `binctl` commands.

## Development (uv)

Contributors can use [uv](https://docs.astral.sh/uv/) for a faster workflow. Generate the ignored
local client first, then install the published `binctl-client` package and other development
dependencies.

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

See [Development](development.md) for more on the project's tooling and CI checks.
