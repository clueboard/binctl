# Development

## Setup with uv

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
PYTHONPATH=.:binctl-client uv run ty check
```

## Tests / CI

The following must pass before merging (run with the venv activated, or via `uv run`):

```bash
pytest
ruff check
PYTHONPATH=.:binctl-client ty check
```

CI (`.github/workflows/ci.yml`) runs `genclient.sh`, `uv sync`, `ruff check`, `ruff format
--check`, `ty check`, and `pytest` on every push to `main` and on every pull request.

## Working on the docs

This site is built with [MkDocs](https://www.mkdocs.org/) and the
[Material theme](https://squidfunk.github.io/mkdocs-material/). Docs dependencies live in the
`docs` dependency group in `pyproject.toml`.

```bash
uv sync --group docs
uv run mkdocs serve
```

`mkdocs serve` starts a local server (default `http://127.0.0.1:8000`) with live reload as you
edit files under `docs/`. Pages are listed in the `nav` section of `mkdocs.yml` — add new pages
there so they show up in the navigation.

Docs are published automatically to the `gh-pages` branch by
`.github/workflows/docs.yml` on every push to `main`. There's no manual publish step.

## Publishing releases

In GitHub Actions, run the `Publish to PyPI` workflow and select the `patch`, `minor`, or `major`
version increment. The workflow runs from `main`, uses `uv version --bump` to update
`pyproject.toml` and `uv.lock`, commits the new version, creates and pushes its matching
`v<version>` tag, and publishes both `binctl-server` and `binctl-client` in the same run. The
workflow regenerates `binctl-client` and syncs its package version to match the server version
before building and publishing both distributions.
