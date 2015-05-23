from functools import wraps

from flask import abort, request
import rollbar

from standardweb import app


VALID_REFERRER_SUBSTRINGS = frozenset((
    'standardsurvival.com', 'www.google.'
))


def reject_external_referrers():
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if (
                not app.config['DEBUG'] and
                request.referrer and
                not any(s in request.referrer for s in VALID_REFERRER_SUBSTRINGS)
            ):
                rollbar.report_message('External referrer blocked', level='warning', request=request)
                abort(401)

            return func(*args, **kwargs)

        return wrapped

    return decorator