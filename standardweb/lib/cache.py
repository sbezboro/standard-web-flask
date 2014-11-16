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
