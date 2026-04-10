# binctl

`binctl` is a tiny graph-based inventory system for people with too many bins, boxes, and shelves.

Instead of thinking in terms of "SKUs" and "stock levels", `binctl` models your world as:

- **nodes** - items, bins, shelves, rooms, etc.
- **edges** - "this thing lives inside that thing".

It's backed by a Flask API with a CLI frontend.

## Setup

1. Copy `.env.example` and fill in your database credentials:
   ```
   cp .env.example .env
   ```
2. Set the `DATABASE_URL` environment variable before starting the server:
   ```
   export DATABASE_URL=mysql+pymysql://user:password@localhost/binctl
   ```
   The format follows SQLAlchemy's URL scheme. MySQL via `pymysql` is the expected driver, but any SQLAlchemy-compatible URL will work.

Current CLI subcommands:

- `binctl node list|get|create|update` - manage nodes
- `binctl tag list|get|create|update`  - manage tags

> **Note:** The API does not yet support DELETE. Nodes and tags can be created
> and updated but not removed via the API.

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
