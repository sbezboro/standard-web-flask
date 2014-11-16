from datetime import datetime
from functools import wraps

from flask import make_response, request


def last_modified(last_modified_func):
    """
    Decorator that will make views return a simple 304 result if
    the provided last_modified_func for the request returns a date
    older than the 'If-Modified-Since' request header.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if_modified_since = request.headers.get('If-Modified-Since')

            response_date = last_modified_func(*args, **kwargs)

            if if_modified_since and response_date:
                if_modified_date = datetime.strptime(if_modified_since, '%a, %d %b %Y %H:%M:%S %Z')

                if if_modified_date >= response_date:
                    response = make_response()
                    response.status_code = 304
                    return response

            resp = f(*args, **kwargs)

            if response_date:
                resp.last_modified = response_date

            return resp

        return wrapped

    return decorator
