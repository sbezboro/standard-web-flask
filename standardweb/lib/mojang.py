import requests

import exceptions
from standardweb.lib import cache


@cache.CachedResult('get_player_profile', time=300)
def get_player_profile(uuid):
    resp = requests.get('https://sessionserver.mojang.com/session/minecraft/profile/%s' % uuid)

    if resp.status_code == 429:
        raise exceptions.RemoteRateLimitException()

    return resp.json()
