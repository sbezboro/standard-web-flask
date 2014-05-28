from datetime import datetime
from datetime import timedelta

from standardweb.lib import cache
from standardweb.models import *

from sqlalchemy.orm import joinedload


def extract_face(image, size):
    try:
        pix = image.load()
        for x in xrange(8, 16):
            for y in xrange(8, 16):
                # apply head accessory for non-transparent pixels
                if pix[x + 32, y][3] > 0:
                    pix[x, y] = pix[x + 32, y]
    except:
        pass

    return image.crop((8, 8, 16, 16)).resize((size, size))


@cache.CachedResult('player', time=30)
def get_server_data(server, player):
    """
    Returns a dict of all the data for a particular player on
    a particular server, or None if the player hasn't played on
    the given server yet.
    """
    stats = PlayerStats.query.options(
        joinedload(PlayerStats.group)
    ).filter_by(server_id=server.id, player_id=player.id).first()
    if not stats:
        return stats

    pvp_kills = []
    pvp_deaths = []
    other_kills = []
    other_deaths = []

    pvp_kill_count = 0
    pvp_death_count = 0
    other_kill_count = 0
    other_death_count = 0

    deaths = DeathCount.query.filter_by(server_id=server.id, victim_id=player.id) \
        .options(joinedload('killer')).options(joinedload('death_type'))

    for death in deaths:
        if death.killer:
            pvp_deaths.append({
                'player': death.killer,
                'count': death.count
            })
            pvp_death_count += death.count
        else:
            other_deaths.append({
                'type': death.death_type.displayname,
                'count': death.count
            })
            other_death_count += death.count

    kills = KillCount.query.filter_by(server_id=server.id, killer_id=player.id) \
        .options(joinedload('kill_type'))

    for kill in kills:
        other_kills.append({
            'type': kill.kill_type.displayname,
            'count': kill.count
        })
        other_kill_count += kill.count

    kills = DeathCount.query.filter_by(server_id=server.id, killer_id=player.id) \
        .options(joinedload('victim')).options(joinedload('death_type'))

    for kill in kills:
        pvp_kills.append({
            'player': kill.victim,
            'count': kill.count
        })
        pvp_kill_count += kill.count

    pvp_kills = sorted(pvp_kills, key=lambda k: (-k['count'], k['player'].displayname.lower()))
    pvp_deaths = sorted(pvp_deaths, key=lambda k: (-k['count'], k['player'].displayname.lower()))
    other_deaths = sorted(other_deaths, key=lambda k: (-k['count'], k['type']))
    other_kills = sorted(other_kills, key=lambda k: (-k['count'], k['type']))

    return {
        'rank': stats.rank,
        'banned': stats.banned,
        'online_now': stats.is_online,
        'first_seen': h.iso_date(stats.first_seen),
        'last_seen': h.iso_date(stats.last_seen),
        'time_spent': h.elapsed_time_string(stats.time_spent),
        'pvp_kills': pvp_kills,
        'pvp_deaths': pvp_deaths,
        'other_kills': other_kills,
        'other_deaths': other_deaths,
        'pvp_kill_count': pvp_kill_count,
        'pvp_death_count': pvp_death_count,
        'other_kill_count': other_kill_count,
        'other_death_count': other_death_count,
        'pvp_logs': stats.pvp_logs,
        'group': stats.group
    }
