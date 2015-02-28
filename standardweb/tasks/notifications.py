from sqlalchemy.orm import joinedload
from standardweb import celery
from standardweb.lib import api, email, notifications, realtime
from standardweb.models import Notification, User, ForumPost, ForumTopicSubscription


@celery.task()
def notify(notification_id):
    notification = Notification.query.get(notification_id)

    user = notification.user
    player = notification.player

    if user:
        realtime.unread_notification_count(user)
        email.send_notification_email(user, notification)

    if notification.can_notify_ingame and player:
        api.new_notification(player, notification)


@celery.task()
def notify_news_post_all(forum_post_id):
    users = User.query.filter(
        User.email != None
    )

    for user in users:
        Notification.create(
            notifications.NEWS_POST,
            user_id=user.id,
            player_id=user.player_id,
            post_id=forum_post_id
        )


@celery.task()
def notify_subscribed_topic_post(forum_post_id):
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
