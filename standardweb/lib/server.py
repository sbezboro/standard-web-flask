import calendar
from datetime import datetime
from datetime import timedelta
import math

from sqlalchemy.orm import joinedload

from standardweb.lib import api
from standardweb.lib import cache
from standardweb.lib import helpers as h
from standardweb.models import PlayerStats, Player, ServerStatus


@cache.CachedResult('ranking')
def get_ranking_data(server):
    retval = []

    player_stats = PlayerStats.query.filter_by(server=server) \
        .order_by(PlayerStats.time_spent.desc()) \
        .limit(40) \
        .options(joinedload('player')) \

    for stats in player_stats:
        online_now = datetime.utcnow() - timedelta(minutes=1) < stats.last_seen

        retval.append((stats.player, h.elapsed_time_string(stats.time_spent), online_now))

    return retval


@cache.CachedResult('player-list', time=5)
def get_player_list_data(server):
    server_status = api.get_server_status(server)

    if not server_status:
        return None

    server_status['players'].sort(key=lambda x: (x.get('nickname') or x['username']).lower())

    player_info = []
    top10_player_ids = PlayerStats.query.filter_by(server=server) \
                           .order_by(PlayerStats.time_spent.desc()) \
                           .limit(10) \
                           .options(joinedload('player'))

    usernames = [x['username'] for x in server_status['players']]
    players = list(Player.query.filter(Player.username.in_(usernames)))
    for player in players:
        rank = None
        if player.id in top10_player_ids:
            for index, top10player_id in enumerate(top10_player_ids):
                if player.id == top10player_id:
                    rank = index + 1

        player_info.append((player, rank))

    # Create player objects for players that don't exist on the server yet
    missing_usernames = set(usernames) - set(player.username for player in players)
    missing_players = [Player.factory(username=username) for username in missing_usernames]
    for player in missing_players:
        player_info.append((player, None))

    player_info.sort(key=lambda x: x[0].displayname.lower())

    try:
        tps = int(math.ceil(float(server_status['tps'])))
    except ValueError:
        tps = 'N/A'

    return {
        'player_info': player_info,
        'num_players': server_status['numplayers'],
        'max_players': server_status['maxplayers'],
        'tps': tps
    }


def get_player_graph_data(server, granularity=15, start_date=None, end_date=None):
    end_date = end_date or datetime.utcnow()
    start_date = start_date or end_date - timedelta(days=7)

    statuses = ServerStatus.query.filter(ServerStatus.server == server,
                                         ServerStatus.timestamp > start_date,
                                         ServerStatus.timestamp < end_date) \
        .order_by('timestamp')

    index = 0
    points = []
    for status in statuses:
        if index % granularity == 0:
            data = {
                'time': int(calendar.timegm(status.timestamp.timetuple()) * 1000),
                'player_count': status.player_count
            }

            points.append(data)

        index += 1

    points.sort(key=lambda x: x['time'])

    return {
        'start_time': int(calendar.timegm(start_date.timetuple()) * 1000),
        'end_time': int(calendar.timegm(end_date.timetuple()) * 1000),
        'points': points
    }
