# CLI reference

`binctl` is the client-side command line tool. It talks to a running server over HTTP.

## Global flags

These flags apply to every `binctl` invocation and must come before the subcommand:

| Flag | Description |
|---|---|
| `--base-url` | API server URL (default: `http://localhost:5000`) |
| `--token` | Bearer token (preferred) |
| `--username` | Username for login-based authentication |
| `--password` | Password for login-based authentication. Visible in process listings (`ps`, `top`) — prefer `--token` for production use. |
| `-o`, `--output` | Output format: `text` (human-friendly, default) or `json` (raw JSON, no spinner) |

```bash
binctl --token $TOKEN <subcommand> ...
```

## Nodes

```
binctl node list|get|create|update|delete [options]
```

| Flag | Applies to | Description |
|---|---|---|
| `action` | all | One of `list`, `get`, `create`, `update`, `delete` |
| `--node-id` | get, update, delete | Node ID to operate on |
| `--label` | create, update | Node label |
| `--description` | create, update | Free-text description |
| `--is-container` | create, update | Set the container flag (create defaults to `false`) |
| `--parent-id` | create, update | Parent node ID |
| `--no-parent` | update | Detach the node from its parent |
| `--tag-id` | create, update | Tag ID(s) to attach/replace; repeatable |

`node update` requires at least one field to change, and rejects `--parent-id` combined with
`--no-parent`.

### Examples

```bash
# Create a container
binctl --token $TOKEN node create --label "Garage" --is-container

# Create an item inside a container
binctl --token $TOKEN node create --label "Power drill" --parent-id <parent-id>

# List all nodes
binctl --token $TOKEN node list

# Get a single node
binctl --token $TOKEN node get --node-id <node-id>

# Move a node to a new parent
binctl --token $TOKEN node update --node-id <node-id> --parent-id <new-parent-id>

# Detach a node (make it a root node)
binctl --token $TOKEN node update --node-id <node-id> --no-parent

# Delete a node
binctl --token $TOKEN node delete --node-id <node-id>
```

## Tags

```
binctl tag list|get|create|update|delete [options]
```

| Flag | Applies to | Description |
|---|---|---|
| `action` | all | One of `list`, `get`, `create`, `update`, `delete` |
| `--tag-id` | get, update, delete | Tag ID to operate on |
| `--name` | create, update | Tag name |

### Examples

```bash
binctl --token $TOKEN tag create --name "fragile"
binctl --token $TOKEN tag list
binctl --token $TOKEN tag update --tag-id <tag-id> --name "handle-with-care"
binctl --token $TOKEN tag delete --tag-id <tag-id>
```

## JSON output

Pass `-o json` (or `--output json`) to get raw JSON instead of the human-friendly text output —
useful for scripting:

```bash
binctl --token $TOKEN -o json node list | jq '.items[] | .label'
```
