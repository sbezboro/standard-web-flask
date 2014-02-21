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
