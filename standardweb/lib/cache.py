from flask import make_response
from flask import request

from standardweb import cache

from datetime import datetime
from functools import wraps


class CachedResult(object):
    """
    Argument based cache
    """
    def __init__(self, prefix, time=60):
        self.prefix = prefix
        self.time = time

    def __call__(self, fn):
        def decorator(*args, **kwargs):
            result = cache.get(self._cache_key(*args, **kwargs))

            if not result:
                result = fn(*args, **kwargs)
                cache.set(self._cache_key(*args, **kwargs), result, self.time)

            return result

        return decorator

    def _cache_key(self, *args, **kwargs):
        key = self.prefix + '-' + '-'.join([str(getattr(arg, 'id', arg)) for arg in args])
        return key


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