# binctl

`binctl` is a tiny graph-based inventory system for people with too many bins, boxes, and shelves.

Instead of thinking in terms of "SKUs" and "stock levels", `binctl` models your world as:

- **nodes** — items, bins, shelves, rooms, etc.
- **edges** — "this thing lives inside that thing".

It's backed by a Flask API with a CLI frontend.

## Where to start

- New to binctl? Head to [Quickstart](quickstart.md) to get a local SQLite instance running in a few minutes.
- Setting up a shared server? See [Installation](installation.md) and [Configuration](configuration.md).
- Want the mental model behind nodes, edges, and tags? Read [Concepts](concepts.md).
- Looking for a specific command? See the [CLI reference](cli.md).
- Contributing code? See [Development](development.md).

## Project links

- [Source on GitHub](https://github.com/clueboard/binctl)
- [PyPI package](https://pypi.org/project/binctl-server/)
- [Issue tracker](https://github.com/clueboard/binctl/issues)
