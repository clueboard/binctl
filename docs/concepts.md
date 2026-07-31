# Concepts

## Nodes

Everything is a node:

- items (tools, parts, one-off widgets)
- containers (bins, boxes, drawers)
- higher-level containers (shelves, rooms, buildings)

Nodes live in the `nodes` table:

| Column | Description |
|---|---|
| `id` | BIGINT primary key |
| `label` | Human-readable name |
| `description` | Optional free text |
| `is_container` | `TRUE` if this node can contain children |

Node IDs are opaque, base62-encoded strings (e.g. `wGIDjZ0AAC`), not sequential integers. Always
copy them from command output — don't guess or construct them by hand.

## Edges

Containment is modeled via the `edges` table:

- `parent_id` → `child_id`
- each child has **at most one parent** (enforced by a UNIQUE constraint)
- self-loops are rejected (`parent_id <> child_id`)

This gives you a **forest of trees**:

- top-level nodes (rooms, "unplaced items") have no parent
- containers and items have exactly one parent
- containers can have many children

### Deleting a container

When you delete a container, its direct children need somewhere to go. If `ORPHAN_LOCATION` is
set (see [Configuration](configuration.md#orphan-handling)), the server looks up a container by
that label at delete time. If no matching container exists outside the deleted subtree, one is
created automatically as a new root container, and the orphaned children are reattached to it.

## Tags

Tags are stored in `tags` + `tag_node` for future filtering and categorization. They're exposed
via `binctl tag list|get|create|update|delete` — see the [CLI reference](cli.md#tags).

Tags can be attached to a node at creation time or replaced on update using `--tag-id` (repeatable).
