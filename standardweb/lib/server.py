import calendar
from datetime import datetime
from datetime import timedelta
import math
import time

from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import label
from standardweb import db

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
    server_status = api.get_server_status(server, minimal=True)

    if not server_status:
        return None

    server_status['players'].sort(key=lambda x: (x.get('nickname') or x['username']).lower())

    usernames = [x['username'] for x in server_status['players']]
    players = Player.query.filter(
        Player.username.in_(usernames)
    ).all()

    # Create player objects for players that don't exist on the server yet
    missing_usernames = set(usernames) - set(player.username for player in players)
    for username in missing_usernames:
        players.append(
            Player(username=username)
        )

    players.sort(key=lambda p: p.displayname.lower())

    try:
        tps = int(round(float(server_status['tps'])))
    except ValueError:
        tps = 'N/A'

    return {
        'players': players,
        'server_id': server.id,
        'num_players': server_status['numplayers'],
        'max_players': server_status['maxplayers'],
        'tps': tps
    }


@cache.CachedResult('player-graph', time=240)
def get_player_graph_data(server, granularity=15, start_date=None, end_date=None):
    end_date = end_date or datetime.utcnow()
    start_date = start_date or end_date - timedelta(days=7)

    result = db.session.query(
        label(
            'timestamp_group',
            func.round(
                (func.unix_timestamp(ServerStatus.timestamp) - time.timezone) / (granularity * 60)
            ),
        ),
        func.avg(ServerStatus.player_count)
    ).filter(
        ServerStatus.server == server,
        ServerStatus.timestamp >= start_date,
        ServerStatus.timestamp <= end_date
    ).group_by('timestamp_group').order_by(
        ServerStatus.timestamp
    ).all()

    points = []
    for chunk, count in result:
        points.append({
            'time': int(chunk * granularity * 60 * 1000),
            'player_count': int(count)
        })

    return {
        'start_time': int(calendar.timegm(start_date.timetuple()) * 1000),
        'end_time': int(calendar.timegm(end_date.timetuple()) * 1000),
        'points': points
    }
