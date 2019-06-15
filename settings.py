from datetime import timedelta

DEBUG = False

WTF_CSRF_ENABLED = False

MEMCACHED_URLS = ['127.0.0.1:11211']

PERMANENT_SESSION_LIFETIME = timedelta(days=3650)

CELERY_BROKER_URL = 'amqp://guest:guest@localhost:5672//'
CELERY_RESULT_BACKEND = 'amqp://guest:guest@localhost:5672//'
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['application/json']

STATSD_HOST = '127.0.0.1'
STATSD_PORT = 8125

GRAPHITE_HOST = '127.0.0.1'
GRAPHITE_PORT = 2003

ASSETS_DEBUG = False
ASSETS_AUTO_BUILD = False
UGLIFYJS_EXTRA_ARGS = ['-c', '-m']

FLASK_ASSETS_USE_CDN = True
CDN_DOMAIN = 'standardsurvival.com'

BLACKLIST_EMAIL_DOMAINS = set([])

BAD_POST_THRESHOLD = -1.0

EXCELLENT_SCORE_THRESHOLD = 3.0
GREAT_SCORE_THRESHOLD = 2.0
GOOD_SCORE_THRESHOLD = 1.0
BAD_SCORE_THRESHOLD = -1.0
TERRIBLE_SCORE_THRESHOLD = -2.0
ABYSMAL_SCORE_THRESHOLD = -3.0

MINIMUM_FORUM_POST_PLAYER_TIME = 1440

IP_LOOKUP_WHITELIST = set([])

# entity identifier, label
KILL_LEADERBOARDS = (
    ('creeper', 'Creeper Kills'),
    ('witch', 'Witch Kills'),
    ('bat', 'Bat Kills'),
    ('squid', 'Squid Kills'),
    ('wither', 'Wither Kills'),
    ('ghast', 'Ghast Kills'),
    ('enderdragon', 'Ender Dragon Kills'),
    ('elderguardian', 'Elder Guardian Kills'),
    ('shulker', 'Shulker Kills'),
)

# meterial identifier, label
ORE_LEADERBOARDS = (
    ('DIAMOND_ORE', 'Diamond Ore Discoveries'),
    ('EMERALD_ORE', 'Emerald Ore Discoveries'),
    ('LAPIS_ORE', 'Lapis Ore Discoveries'),
    ('REDSTONE_ORE', 'Redstone Ore Discoveries'),
    ('NETHER_QUARTZ_ORE', 'Quartz Ore Discoveries'),
    ('COAL_ORE', 'Coal Ore Discoveries'),
)

try:
    from local_settings import *
except ImportError:
    pass
