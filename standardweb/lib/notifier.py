from standardweb.lib import api
from standardweb.lib import email
from standardweb.lib import realtime
from standardweb.tasks.notifications import (
    create_news_post_notifications_task,
    create_subscrobed_post_notifications_task,
    notification_notify_task
)


def notify_new_message(message):
    from_user = message.from_user
    to_user = message.to_user
    to_player = message.to_player

    if to_user:
        realtime.new_message(message)
        realtime.unread_message_count(to_user)
        email.send_new_message_email(to_user, message)

    if to_player:
        api.new_message(to_player, from_user)


def notify_message_read(message):
    realtime.message_read(message)


def notification_notify(notification, send_email=True):
    notification_notify_task.apply_async((
        notification.id, send_email
    ))


def create_news_post_notifications(post, email_all=True):
    create_news_post_notifications_task.apply_async((
        post.id, email_all
    ))


def create_subscribed_post_notifications(post):
    create_subscrobed_post_notifications_task.apply_async((
        post.id,
    ))
