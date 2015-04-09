from datetime import datetime, timedelta
import requests

from sqlalchemy.sql import func
import rollbar

from standardweb import app, celery, db
from standardweb.lib import minecraft_uuid
from standardweb.models import Player, PlayerStats


def paged_query(query, limit=None):
    offset = 0
    if limit is None:
        limit = 100

    while True:
        rows = query.offset(offset).limit(limit)

        for row in rows:
            yield row

        offset += limit


@celery.task()
def schedule_checks():
    # check latest username for players that have been offline for at least a day
    query = db.session.query(
        Player.uuid
    ).join(
        PlayerStats
    ).group_by(
        Player.uuid
    ).having(
        func.max(PlayerStats.last_seen) < datetime.utcnow() - timedelta(days=1)
    ).order_by(Player.id)

    rollbar.report_message('Scheduling %d uuids for username change checks' % query.count(), level='info')

    # schedule a uuid check once every 6 seconds to spread across a week
    for i, row in enumerate(paged_query(query)):
        player_uuid = row.uuid

        check_uuid.apply_async(
            args=(player_uuid,),
            countdown=i * 6
        )


@celery.task()
def check_uuid(player_uuid):
    player = Player.query.filter_by(uuid=player_uuid).first()
    stats = PlayerStats.query.filter_by(
        player=player, server_id=app.config.get('MAIN_SERVER_ID')
    ).first()

    if stats and stats.last_seen > datetime.utcnow() - timedelta(days=1):
        # ignore players that have joined since the job started
        return

    try:
        actual_username = minecraft_uuid.lookup_latest_username_by_uuid(player_uuid)
    except requests.RequestException:
        return

    if not actual_username:
        return

    if actual_username != player.username:
        player.set_username(actual_username)
        player.save(commit=True)
