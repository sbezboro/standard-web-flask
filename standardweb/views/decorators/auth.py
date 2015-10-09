from functools import wraps

from flask import abort, flash, g, redirect, request, url_for


def login_required(show_message=True, only_moderator=False, only_admin=False):
    """
    Decorator that will redirect the user to the login page
    if they aren't logged in. Raises a 403 if the view requires
    an admin and the user isn't an admin
    """
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if not g.user:
                if show_message:
                    flash('You must log in first', 'warning')

                next = None
                if request.path not in (url_for('index'), url_for('login')):
                    next = request.path

                return redirect(url_for('login', next=next))

            if only_admin and not g.user.admin:
                abort(403)

            if only_moderator and not g.user.admin and not g.user.moderator:
                abort(403)

            return func(*args, **kwargs)

        return wrapped

    return decorator
