DEBUG = False

WTF_CSRF_ENABLED = False

try:
    from local_settings import *
except ImportError:
    pass
