#!/usr/bin/env sh
set -eu

uvx --from 'openapi-python-client>=0.21' openapi-python-client generate --path openapi.yaml --overwrite --custom-template-path templates/
