from functools import wraps

from flask import request, redirect

from standardweb import app


def ssl_required():
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if app.config.get('SSL_REDIRECTION'):
                if request.is_secure:
                    return func(*args, **kwargs)
                else:
                    return redirect(request.url.replace('http://', 'https://'))

            return func(*args, **kwargs)

        return wrapped

    return decorator
