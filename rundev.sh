#!/bin/sh
uvicorn 'binctl_server.web:create_app' --factory --reload
