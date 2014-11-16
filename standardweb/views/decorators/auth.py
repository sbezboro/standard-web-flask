from functools import wraps

from flask import flash, g, redirect, request, url_for


def login_required(show_message=True):
    """
    Decorator that will redirect the user to the login page
    if they aren't logged in.
    """
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if not g.user:
                if show_message:
                    flash('You must log in first', 'warning')

                return redirect(url_for('login', next=request.path))

            return func(*args, **kwargs)

        return wrapped

    return decorator
