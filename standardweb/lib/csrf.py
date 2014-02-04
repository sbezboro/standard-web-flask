from flask import session

from functools import wraps
import os

exempt_funcs = set()


def exempt(f):
    exempt_funcs.add(f)

    @wraps(f)
    def wrapped(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapped


def _generate_token():
    return os.urandom(20).encode('hex')


def get_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = _generate_token()

    return session['csrf_token']


def regenerate_token():
    session['csrf_token'] = _generate_token()
    return session['csrf_token']
