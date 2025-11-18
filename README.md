# binctl

`binctl` is a tiny graph-based inventory system for people with too many bins, boxes, and shelves.

Instead of thinking in terms of "SKUs" and "stock levels", `binctl` models your world as:

- **nodes** - items, bins, shelves, rooms, etc.
- **edges** - "this thing lives inside that thing".

It's backed by a Flask API with a CLI frontend, so you can:

- create nodes for items and containers
- move things between containers
- locate any item by walking the container tree
- generate labels for bins/items for barcode/Qr usage

Current CLI subcommands:

- `binctl create` - create items and containers
- `binctl move`   - move a node under a new parent
- `binctl locate` - show where something lives
- `binctl label`  - generate label data for a node

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

The initial CLI focuses on the core graph operations; tagging is wired into the schema and ready to be exposed later.
