from standardweb.lib import api
from standardweb.lib import email
from standardweb.lib import realtime
from standardweb.tasks.notifications import (
    notify as notify_task,
    notify_news_post_all as notify_news_post_all_task,
    notify_subscribed_topic_post as notify_subscribed_topic_post_task
)


def notify_new_message(message):
    from_user = message.from_user
    to_user = message.to_user
    to_player = message.to_player

    if to_user:
        realtime.new_message(to_user, message)
        realtime.unread_message_count(to_user)
        email.send_new_message_email(to_user, message)

    if to_player:
        api.new_message(to_player, from_user)


def notify(notification):
    notify_task.apply_async((
        notification.id,
    ))


def notify_news_post(post):
    notify_news_post_all_task.apply_async((
        post.id,
    ))


def notify_subscribed_topic_post(post):
    notify_subscribed_topic_post_task.apply_async((
        post.id,
    ))
