import logging
import logging.config
import os

import connexion
from connexion.middleware import MiddlewarePosition
from flask import g, jsonify
from starlette.middleware.cors import CORSMiddleware

_LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'structured': {
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
            'datefmt': '%Y-%m-%dT%H:%M:%S%z',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'structured',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
}


def create_app():
    logging.config.dictConfig(_LOGGING_CONFIG)

    cors_origins_raw = os.environ.get('CORS_ORIGINS', '')
    if cors_origins_raw.strip() == '*':
        raise ValueError("CORS_ORIGINS='*' is not allowed; specify explicit origins")
    allow_origins = [o.strip() for o in cors_origins_raw.split(',') if o.strip()]

    _cors_max_age_raw = os.environ.get('CORS_MAX_AGE', '600')
    try:
        max_age = int(_cors_max_age_raw)
    except ValueError:
        raise ValueError(f'CORS_MAX_AGE must be an integer (got {_cors_max_age_raw!r})')

    cx_app = connexion.App(__name__, specification_dir='.')
    cx_app.add_api('openapi.yaml', strict_validation=True, validate_responses=True)
    cx_app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
        max_age=max_age,
    )

    # App teardown
    cx_app.app.teardown_appcontext(close_db)

    return cx_app


def close_db(exc=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def error(status, message):
    resp = jsonify({'error': message})
    resp.status_code = status

    return resp
