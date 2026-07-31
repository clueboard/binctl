# Quickstart

The fastest path to a running system, using SQLite for local development. Requires Python 3.11+.
Run each block in your terminal.

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

## Building an inventory

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

Next: read up on the [concepts](concepts.md) behind nodes, edges, and tags, or dig into the full
[CLI reference](cli.md).
