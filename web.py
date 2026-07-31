import importlib.resources
import logging
import logging.config
import os
import pathlib

import connexion
from connexion.middleware import MiddlewarePosition
from dotenv import load_dotenv
from flask import g, jsonify
from starlette.middleware.cors import CORSMiddleware

# openapi.yaml lives in the binctl_spec package (rather than next to this module) so it can be
# shipped as package data — plain top-level modules like this one can't carry package data of
# their own, so a spec file placed next to web.py would go missing from the installed wheel.
# importlib.resources.files() returns a Traversable, which connexion's add_api() doesn't accept,
# so convert it to a concrete pathlib.Path.
_OPENAPI_SPEC = pathlib.Path(str(importlib.resources.files('binctl_spec') / 'openapi.yaml'))

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
    """Create and configure the Connexion/Flask application.

    Reads configuration from environment variables (loaded from .env if present):
    - DATABASE_URL (required)
    - CORS_ORIGINS, CORS_MAX_AGE — cross-origin request policy
    - SESSION_LIFETIME_DAYS — web session token lifetime (default: 30)
    - ORPHAN_LOCATION — container label for children of deleted containers (optional)
    """
    load_dotenv()
    logging.config.dictConfig(_LOGGING_CONFIG)

    cors_origins_raw = os.environ.get('CORS_ORIGINS', '')
    if cors_origins_raw.strip() == '*':
        raise ValueError("CORS_ORIGINS='*' is not allowed; specify explicit origins")
    allow_origins = [o.strip() for o in cors_origins_raw.split(',') if o.strip()]
    if not allow_origins:
        logging.warning('CORS_ORIGINS is empty. Since allow_credentials=True, all cross-origin credentialed requests will be rejected.')

    _cors_max_age_raw = os.environ.get('CORS_MAX_AGE', '600')
    try:
        max_age = int(_cors_max_age_raw)
    except ValueError:
        raise ValueError(f'CORS_MAX_AGE must be an integer (got {_cors_max_age_raw!r})')

    _session_lifetime_raw = os.environ.get('SESSION_LIFETIME_DAYS', '30')
    try:
        session_lifetime_days = int(_session_lifetime_raw)
        if session_lifetime_days <= 0:
            raise ValueError
    except ValueError:
        raise ValueError(f'SESSION_LIFETIME_DAYS must be a positive integer (got {_session_lifetime_raw!r})')

    cx_app = connexion.App(__name__)
    cx_app.app.config['SESSION_LIFETIME_DAYS'] = session_lifetime_days
    cx_app.app.config['ORPHAN_LOCATION'] = os.environ.get('ORPHAN_LOCATION') or None  # `or None` allows the user to set ORPHAN_LOCATION to an empty string.
    cx_app.add_api(_OPENAPI_SPEC, strict_validation=True, validate_responses=True)
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
