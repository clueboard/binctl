import connexion
from flask import g, jsonify


def create_app():
    # App setup
    cx_app = connexion.App(__name__, specification_dir='.')
    cx_app.add_api('openapi.yaml', strict_validation=True, validate_responses=False)

    # App teardown
    cx_app.app.teardown_appcontext(close_db)

    return cx_app.app


def close_db(exc=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def error(status, message):
    resp = jsonify({'error': message})
    resp.status_code = status

    return resp
