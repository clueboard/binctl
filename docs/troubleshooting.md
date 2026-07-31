# Troubleshooting

**`ModuleNotFoundError: No module named 'binctl_client'`**

Reinstall the project dependencies with `pip install -e .` or `uv sync`.

**`Connection refused` / `Failed to connect` when running `binctl` commands**

The server is not running. Start it with `uvicorn web:create_app --factory` (binds to
`http://localhost:5000` by default). If you changed the port, pass
`--base-url http://localhost:<port>` to `binctl`.

**`401 Unauthorized`**

Token is missing or wrong. Re-create one with `python manage.py create-user alice --token`, or
list existing tokens with `python manage.py list-tokens alice`.

**`DATABASE_URL not set` or database errors on startup**

Export the variable before running server or manage commands:

```bash
export DATABASE_URL=sqlite:///binctl.db
```

Or add it to your `.env` file (copied from `.env.example`) — see [Configuration](configuration.md).
