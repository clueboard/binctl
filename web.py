import logging
import logging.config

import connexion
from flask import g, jsonify

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
    cx_app = connexion.App(__name__, specification_dir='.')
    cx_app.add_api('openapi.yaml', strict_validation=True, validate_responses=True)

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
