from datetime import datetime, timedelta
import rollbar

from sqlalchemy.sql import func

from standardweb import celery, db
from standardweb.lib import minecraft_uuid
from standardweb.models import AuditLog, Player, PlayerStats


def paged_query(query, limit=None):
    offset = 0
    if limit is None:
        limit = 100

    while True:
        rows = query.offset(offset).limit(limit).all()

        if not rows:
            return

        yield rows

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

    i = 0

    rollbar.report_message('Checking %d uuids for username changes' % query.count())

    # group uuid checks in groups of 100 every minute
    for rows in paged_query(query):
        player_uuids = [x.uuid for x in rows]

        check_uuids.apply_async(
            args=(player_uuids,),
            countdown=i * 60
        )

        i += 1


@celery.task()
def check_uuids(player_uuids):
    num_changed = 0

    for uuid in player_uuids:
        player = Player.query.filter_by(uuid=uuid).first()

        try:
            actual_username = minecraft_uuid.lookup_latest_username_by_uuid(uuid)
        except Exception:
            continue

        if actual_username != player.username:
            AuditLog.create(
                AuditLog.PLAYER_RENAME,
                player_id=player.id,
                old_name=player.username,
                new_name=actual_username,
                commit=False
            )

            player.username = actual_username
            player.save(commit=False)

            num_changed += 1

    db.session.commit()

    rollbar.report_message('Finished checking uuid group', extra_data={
        'num_changed': num_changed
    })
