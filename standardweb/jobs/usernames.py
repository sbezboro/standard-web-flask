from datetime import datetime, timedelta
import requests

import rollbar

from standardweb import app, cache, celery, db
from standardweb.lib import helpers as h
from standardweb.lib import minecraft_uuid
from standardweb.models import Player, PlayerStats


COUNTER_CACHE_NAME = 'jobs.usernames.player_offset'
PLAYERS_PER_JOB = 100


def _get_players(offset):
    return Player.query.join(
        PlayerStats
    ).order_by(
        Player.id
    ).limit(
        PLAYERS_PER_JOB
    ).offset(
        offset
    ).all()


@celery.task()
def check_uuids():
    num_changed = 0

    offset = cache.get(COUNTER_CACHE_NAME) or 0

    players = _get_players(offset)

    if not players:
        rollbar.report_message('All players checked, check_uuids wrapping around', level='info', extra_data={
            'offset': offset
        })
        offset = 0
        players = _get_players(offset)

    for player in players:
        stats = PlayerStats.query.filter_by(
            player=player, server_id=app.config.get('MAIN_SERVER_ID')
        ).first()

        if stats and stats.last_seen > datetime.utcnow() - timedelta(days=1):
            # ignore players that have joined since the job started
            continue

        try:
            actual_username = minecraft_uuid.lookup_latest_username_by_uuid(player.uuid)
        except requests.RequestException as e:
            rollbar.report_message('Exception looking up uuid, skipping group', level='warning', extra_data={
                'num_changed': num_changed,
                'exception': unicode(e)
            })
            return

        if not actual_username:
            rollbar.report_message('Error getting actual username, skipping', level='warning', extra_data={
                'uuid': player.uuid
            })
            continue

        if actual_username != player.username:
            h.avoid_duplicate_username(actual_username, player.uuid)

            player.set_username(actual_username)
            player.save(commit=False)

            num_changed += 1

    db.session.commit()

    cache.set(COUNTER_CACHE_NAME, offset + PLAYERS_PER_JOB)

    rollbar.report_message('Finished checking uuid group', level='info', extra_data={
        'offset': offset,
        'num_changed': num_changed
    })
