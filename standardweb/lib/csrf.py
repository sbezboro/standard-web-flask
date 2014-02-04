from functools import wraps

exempt_funcs = set()


def exempt(f):
    exempt_funcs.add(f)

    @wraps(f)
    def wrapped(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapped