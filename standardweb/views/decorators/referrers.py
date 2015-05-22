from functools import wraps

from flask import abort, request
import rollbar

from standardweb import app


def reject_external_referrers():
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if not app.config['DEBUG'] and 'standardsurvival.com' not in request.referrer:
                rollbar.report_message('External referrer blocked', level='warning', request=request)
                abort(401)

            return func(*args, **kwargs)

        return wrapped

    return decorator