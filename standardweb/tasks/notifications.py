from datetime import datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from standardweb import celery, db, app
from standardweb.lib import api, email, notifications, realtime
from standardweb.models import ForumBan, ForumPost, ForumTopicSubscription, Notification, Player, PlayerStats, User


@celery.task()
def notification_notify_task(notification_id, send_email):
    notification = Notification.query.get(notification_id)

    user = notification.user
    player = notification.player

    if user:
        realtime.unread_notification_count(user)

        if send_email:
            email.send_notification_email(user, notification)

    if notification.can_notify_ingame and player:
        api.new_notification(player, notification)


@celery.task()
def create_news_post_notifications_task(forum_post_id, email_all):
    # Create notifications for the players active in the past month or all users with valid emails
    recipients = db.session.query(
        Player.id, User.id
    ).outerjoin(
        User
    ).outerjoin(
        ForumBan, ForumBan.user_id == User.id
    ).join(
        PlayerStats
    ).filter(
        or_(
            and_(
                PlayerStats.server_id == app.config.get('MAIN_SERVER_ID'),
                PlayerStats.last_seen > datetime.utcnow() - timedelta(days=30)
            ),
            User.email != None
        )
    ).filter(
        ForumBan.id == None,
        Player.banned == False
    ).distinct(
        Player.id, User.id
    ).all()

    for player_id, user_id in recipients:
        Notification.create(
            notifications.NEWS_POST,
            user_id=user_id,
            player_id=player_id,
            post_id=forum_post_id,
            send_email=email_all
        )


@celery.task()
def create_subscrobed_post_notifications_task(forum_post_id):
    post = ForumPost.query.get(forum_post_id)
    topic = post.topic

    subscriptions = ForumTopicSubscription.query.options(
        joinedload(ForumTopicSubscription.user)
    ).filter(
        ForumTopicSubscription.topic == topic,
        ForumTopicSubscription.user_id != post.user_id
    ).all()

    for subscription in subscriptions:
        Notification.create(
            notifications.SUBSCRIBED_TOPIC_POST,
            user_id=subscription.user.id,
            player_id=subscription.user.player_id,
            post_id=forum_post_id
        )
