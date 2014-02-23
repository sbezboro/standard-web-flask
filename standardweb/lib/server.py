from standardweb.lib import api
from standardweb.lib import helpers as h
from standardweb.models import *

from sqlalchemy.sql.expression import desc
from sqlalchemy.orm import joinedload

from datetime import datetime
from datetime import timedelta


def get_ranking_data(server):
    retval = []

    player_stats = PlayerStats.query.filter_by(server=server) \
        .order_by(desc(PlayerStats.time_spent)) \
        .limit(40) \
        .options(joinedload('player')) \

    for stats in player_stats:
        online_now = datetime.utcnow() - timedelta(minutes = 1) < stats.last_seen

        retval.append((stats.player, h.elapsed_time_string(stats.time_spent), online_now))

    return retval


def get_player_list_data(server):
    server_status = api.get_server_status(server)

    if not server_status:
        return None

    server_status['players'].sort(key=lambda x: (x.get('nickname') or x['username']).lower())

    player_info = []
    top10_player_ids = PlayerStats.query.filter_by(server=server) \
                           .order_by(desc(PlayerStats.time_spent)) \
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

    return {
        'player_info': player_info,
        'num_players': server_status['numplayers'],
        'max_players': server_status['maxplayers'],
        'tps': server_status['tps']
    }
