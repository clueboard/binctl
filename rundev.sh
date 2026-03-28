#!/bin/sh
uvicorn 'web:create_app' --factory --reload
