import os
import pygeoip

from standardweb import app
from standardweb.lib import cache

PROJECT_PATH = os.path.abspath(os.path.dirname(__name__))
BAD_ORG = 'bad_org'

_orgs = [x.lower() for x in app.config.get('BLACKLIST_IP_ORGS', [])]
_gi4 = pygeoip.GeoIP(
    '%s/%s' % (PROJECT_PATH, app.config.get('GEOIP_DB_PATH')),
    pygeoip.MEMORY_CACHE
)


@cache.CachedResult('get_ip_org', time=86400)
def get_ip_org(ip):
    org = _gi4.org_by_addr(ip)
    if org:
        return org

    return BAD_ORG


def is_nok(ip):
    org = get_ip_org(ip)
    if org == BAD_ORG:
        return False

    org = org.lower()

    return any(x in org for x in _orgs)
