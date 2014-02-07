from datetime import datetime
from datetime import timedelta

from standardweb.models import *


def get_server_data(server, player):
    """
    Returns a dict of all the data for a particular player on
    a particular server, or None if the player hasn't played on
    the given server yet.
    """
    stats = PlayerStats.query.filter_by(server_id=server.id, player_id=player.id).first()
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

    deaths = DeathCount.query.filter_by(server_id=server.id, victim_id=player.id)

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

    kills = KillCount.query.filter_by(server_id=server.id, killer_id=player.id)

    for kill in kills:
        other_kills.append({
            'type': kill.kill_type.displayname,
            'count': kill.count
        })
        other_kill_count += kill.count

    kills = DeathCount.query.filter_by(server_id=server.id, killer_id=player.id)

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

    online_now = datetime.utcnow() - timedelta(minutes=1) < stats.last_seen

    return {
        'rank': stats.get_rank(),
        'banned': stats.banned,
        'online_now': online_now,
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
        'pvp_logs': stats.pvp_logs
    }
