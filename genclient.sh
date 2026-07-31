#!/usr/bin/env sh
set -eu

uvx --from 'openapi-python-client>=0.21' openapi-python-client generate --path binctl_spec/openapi.yaml --overwrite --custom-template-path templates/
