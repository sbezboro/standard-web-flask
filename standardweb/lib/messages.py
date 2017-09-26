from datetime import datetime, timedelta

from sqlalchemy import func

from standardweb import app, db
from standardweb.models import Message


# the difference in the amount of messages to a certain user before the sender is blocked
MESSAGE_THROTTLE_DIFFERENCE = 10

# the max number of recipients a sender can have in the throttle period
MESSAGE_THROTTLE_UNIQUE_RECIPIENTS = 5

MESSAGE_THROTTLE_PERIOD = 2  # hours


def is_sender_spamming(user, to_user, to_player):
    if app.config['DEBUG'] or user.admin_or_moderator:
        return False

    recent_unique_recipients = db.session.query(func.count(Message.to_player_id)).filter(
        Message.from_user == user,
        Message.sent_at > datetime.utcnow() - timedelta(hours=MESSAGE_THROTTLE_PERIOD),
        Message.deleted == False
    ).group_by(Message.to_player_id).all()

    if len(recent_unique_recipients) > MESSAGE_THROTTLE_UNIQUE_RECIPIENTS:
        return True

    recent_messages_to_player = Message.query.with_entities(Message.id).filter(
        Message.from_user == user,
        Message.to_player == to_player,
        Message.sent_at > datetime.utcnow() - timedelta(hours=MESSAGE_THROTTLE_PERIOD),
        Message.seen_at == None,
        Message.deleted == False
    ).all()

    if to_user:
        recent_messages_from_user = Message.query.with_entities(Message.id).filter(
            Message.to_user == user,
            Message.from_user == to_user,
            Message.sent_at > datetime.utcnow() - timedelta(hours=MESSAGE_THROTTLE_PERIOD),
            Message.deleted == False
        ).all()
    else:
        recent_messages_from_user = []

    if len(recent_messages_to_player) - len(recent_messages_from_user) > MESSAGE_THROTTLE_DIFFERENCE:
        return True

    return False
