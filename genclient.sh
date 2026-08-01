#!/usr/bin/env sh
set -eu

uvx --from 'openapi-python-client>=0.21' openapi-python-client generate --path binctl_server/openapi.yaml --overwrite --custom-template-path templates/

# Overlay our maintained CLI entrypoint into the generated client package.
mkdir -p binctl-client/binctl_cli
cp binctl_cli/entrypoint.py binctl-client/binctl_cli/entrypoint.py
cp binctl_cli/__init__.py binctl-client/binctl_cli/__init__.py
