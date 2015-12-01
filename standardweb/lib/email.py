import base64
from functools import wraps
import hashlib
import hmac

from flask import render_template
from flask import url_for
import rollbar
from sqlalchemy.orm import joinedload

from standardweb import app
from standardweb.lib import notifications
from standardweb.models import EmailToken, User, ForumPost, Player
from standardweb.tasks.email import send_email_task
from standardweb.tasks.messages import send_new_message_email_task


DEFAULT_FROM_EMAIL = 'Standard Survival <server@standardsurvival.com>'
MESSAGE_REPLY_FROM_EMAIL = 'Standard Survival <message-reply@mail.standardsurvival.com>'
EMAIL_URL = 'https://api.mailgun.net/v2/mail.standardsurvival.com/messages'

# time to collect notifications before sending a batch in one email
EMAIL_BATCH_TIME_SEC = 300

NOTIFICATION_EMAILS = {}


def email_preference_enabled(type):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            for arg in args:
                if isinstance(arg, User):
                    if arg.get_notification_preference(type).email:
                        return func(*args, **kwargs)

        return wrapped

    return decorator


def notification_email(type):
    def decorator(func):
        @wraps(func)
        @email_preference_enabled(type)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        NOTIFICATION_EMAILS[type] = wrapped

        return wrapped

    return decorator


def send_creation_email(to_email, uuid, username):
    email_token = EmailToken.create_creation_token(to_email, uuid, commit=False)

    verify_url = url_for('create_account', token=email_token.token, _external=True)

    text_body, html_body = _render_email('create_account', to_email, {
        'username': username,
        'verify_url': verify_url
    })

    email_token.save(commit=True)

    send_email(to_email, '[Standard Survival] Please verify your email', text_body, html_body)


def send_verify_email(to_email, user):
    email_token = EmailToken.create_verify_token(to_email, user.id, commit=False)

    verify_url = url_for('verify_email', token=email_token.token, _external=True)

    text_body, html_body = _render_email('verify_email', to_email, {
        'username': user.player.username,
        'verify_url': verify_url
    })

    email_token.save(commit=True)

    send_email(to_email, '[Standard Survival] Please verify your email', text_body, html_body)


def send_reset_password(user):
    email_token = EmailToken.create_reset_password_token(user.id, commit=False)

    verify_url = url_for('reset_password', token=email_token.token, _external=True)

    to_email = user.email

    text_body, html_body = _render_email('reset_password', to_email, {
        'verify_url': verify_url
    })

    email_token.save(commit=True)

    return send_email(to_email, '[Standard Survival] Reset password', text_body, html_body)


def schedule_new_message_email(message):
    send_new_message_email_task.apply_async((
        message.id,
    ), countdown=EMAIL_BATCH_TIME_SEC)


@email_preference_enabled('new_message')
def send_new_message_email(user, message):
    to_email = user.email

    if not to_email:
        return

    from_user = message.from_user
    from_username = from_user.get_username()

    conversation_url = url_for('messages', username=from_username, _external=True)

    from_player_url = None
    if from_user.player:
        from_player_url = url_for('player', username=from_user.player.uuid, _external=True)

    unsubscribe_link = notifications.generate_unsubscribe_link(user, 'new_message')

    reply_token = '%s-%s-%s' % (
        base64.b64encode(str(from_user.id)),
        base64.b64encode(str(user.id)),
        _generate_message_reply_signature(from_user.id, user.id)
    )

    text_body, html_body = _render_email('messages/new_message', to_email, {
        'username': user.get_username(),
        'reply_token': reply_token,
        'from_username': from_username,
        'message_body': message.body,
        'message_body_html': message.body_html,
        'conversation_url': conversation_url,
        'from_player_url': from_player_url,
        'unsubscribe_url': unsubscribe_link
    })

    send_email(
        to_email,
        '[Standard Survival] New message from %s' % from_username,
        text_body,
        html_body,
        from_email=MESSAGE_REPLY_FROM_EMAIL
    )


@email_preference_enabled('new_message')
def send_new_messages_email(user, messages):
    to_email = user.email

    if not to_email:
        return

    from_user = messages[0].from_user
    from_username = from_user.get_username()

    conversation_url = url_for('messages', username=from_username, _external=True)

    from_player_url = None
    if from_user.player:
        from_player_url = url_for('player', username=from_user.player.uuid, _external=True)

    unsubscribe_link = notifications.generate_unsubscribe_link(user, 'new_message')

    text_body, html_body = _render_email('messages/new_messages', to_email, {
        'username': user.get_username(),
        'from_username': from_username,
        'num_messages': len(messages),
        'conversation_url': conversation_url,
        'from_player_url': from_player_url,
        'unsubscribe_url': unsubscribe_link
    })

    send_email(
        to_email,
        '[Standard Survival] %s new unread messages from %s' % (len(messages), from_username),
        text_body,
        html_body
    )


@notification_email(notifications.NEWS_POST)
def send_news_post_email(user, notification):
    to_email = user.email

    if not to_email:
        return

    post_id = notification.data['post_id']

    post = ForumPost.query.options(
        joinedload(ForumPost.topic)
    ).get(post_id)

    topic = post.topic

    notifications_url = url_for('notifications', _external=True)
    forum_topic_url = url_for('forum_topic', topic_id=post.topic_id, _external=True)
    unsubscribe_link = notifications.generate_unsubscribe_link(user, notifications.NEWS_POST)

    text_body, html_body = _render_email('notifications/news_post', to_email, {
        'post_body': post.body,
        'post_body_html': post.body_html,
        'topic_url': forum_topic_url,
        'unsubscribe_url': unsubscribe_link,
        'notifications_url': notifications_url
    })

    send_email(to_email, '[Standard Survival] %s' % topic.name, text_body, html_body)


@notification_email(notifications.SUBSCRIBED_TOPIC_POST)
def send_subscribed_topic_post_email(user, notification):
    to_email = user.email

    if not to_email:
        return

    post_id = notification.data['post_id']

    post = ForumPost.query.options(
        joinedload(ForumPost.topic)
    ).options(
        joinedload(ForumPost.user)
        .joinedload(User.player)
    ).get(post_id)

    topic = post.topic
    player = post.user.player

    notifications_url = url_for('notifications', _external=True)
    forum_post_url = url_for('forum_post', post_id=post_id, _external=True)
    topic_url = url_for('forum_topic', topic_id=topic.id, _external=True)
    post_player_url = url_for('player', username=player.uuid, _external=True) if player else None
    unsubscribe_topic_url = url_for('forum_topic_unsubscribe', topic_id=topic.id, _external=True)
    unsubscribe_url = notifications.generate_unsubscribe_link(user, notifications.SUBSCRIBED_TOPIC_POST)

    text_body, html_body = _render_email('notifications/subscribed_topic_post', to_email, {
        'username': user.get_username(),
        'post_body': post.body,
        'post_body_html': post.body_html,
        'post_url': forum_post_url,
        'post_username': post.user.get_username(),
        'post_player': player,
        'post_player_url': post_player_url,
        'topic_url': topic_url,
        'topic_name': topic.name,
        'unsubscribe_topic_url': unsubscribe_topic_url,
        'unsubscribe_url': unsubscribe_url,
        'notifications_url': notifications_url
    })

    send_email(to_email, '[Standard Survival] New reply in the topic "%s"' % topic.name, text_body, html_body)


@notification_email(notifications.GROUP_KICK_IMMINENT)
def send_group_kick_imminent_email(user, notification):
    to_email = user.email

    if not to_email:
        return

    group_name = notification.data['group_name']

    group_url = url_for('group', name=group_name, _external=True)
    notifications_url = url_for('notifications', _external=True)
    unsubscribe_url = notifications.generate_unsubscribe_link(user, notifications.GROUP_KICK_IMMINENT)

    text_body, html_body = _render_email('notifications/group_kick_imminent', to_email, {
        'username': user.get_username(),
        'group_name': group_name,
        'group_url': group_url,
        'unsubscribe_url': unsubscribe_url,
        'notifications_url': notifications_url
    })

    send_email(
        to_email,
        '[Standard Survival] Watch out! You are about to be kicked from your group!',
        text_body,
        html_body
    )


@notification_email(notifications.KICKED_FROM_GROUP)
def send_kicked_from_group_email(user, notification):
    to_email = user.email

    if not to_email:
        return

    group_name = notification.data['group_name']
    kicker_uuid = notification.data.get('kicker_uuid')

    kicker = None
    kicker_url = None
    if kicker_uuid:
        kicker = Player.query.filter_by(uuid=kicker_uuid).first()
        kicker_url = url_for('player', username=kicker.uuid, _external=True)

    group_url = url_for('group', name=group_name, _external=True)
    notifications_url = url_for('notifications', _external=True)
    unsubscribe_url = notifications.generate_unsubscribe_link(user, notifications.KICKED_FROM_GROUP)

    text_body, html_body = _render_email('notifications/kicked_from_group', to_email, {
        'username': user.get_username(),
        'group_name': group_name,
        'group_url': group_url,
        'kicker': kicker,
        'kicker_url': kicker_url,
        'unsubscribe_url': unsubscribe_url,
        'notifications_url': notifications_url
    })

    send_email(
        to_email,
        '[Standard Survival] You were kicked from your group!',
        text_body,
        html_body
    )


@notification_email(notifications.GROUP_DESTROYED)
def send_group_destroyed_email(user, notification):
    to_email = user.email

    if not to_email:
        return

    group_name = notification.data['group_name']
    destroyer_uuid = notification.data.get('destroyer_uuid')

    destroyer = None
    destroyer_url = None
    if destroyer_uuid:
        destroyer = Player.query.filter_by(uuid=destroyer_uuid).first()
        destroyer_url = url_for('player', username=destroyer.uuid, _external=True)

    notifications_url = url_for('notifications', _external=True)
    unsubscribe_url = notifications.generate_unsubscribe_link(user, notifications.GROUP_DESTROYED)

    text_body, html_body = _render_email('notifications/group_destroyed', to_email, {
        'username': user.get_username(),
        'group_name': group_name,
        'destroyer': destroyer,
        'destroyer_url': destroyer_url,
        'unsubscribe_url': unsubscribe_url,
        'notifications_url': notifications_url
    })

    send_email(
        to_email,
        '[Standard Survival] Your group was destroyed!',
        text_body,
        html_body
    )


def send_notification_email(user, notification):
    func = NOTIFICATION_EMAILS.get(notification.type)

    if func:
        func(user, notification)


def send_email(to_email, subject, text_body, html_body, from_email=None):
    if not to_email:
        return

    if any(x in to_email for x in app.config['BLACKLIST_EMAIL_DOMAINS']):
        rollbar.report_message('Blacklisted email blocked', level='error', extra_data=dict(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body
        ))
        return

    send_email_task.apply_async((
        from_email or DEFAULT_FROM_EMAIL,
        to_email,
        subject,
        text_body,
        html_body
    ))


def verify_mailgun_signature(api_key, token, timestamp, signature):
    expected_signature = hmac.new(
        key=api_key,
        msg='{}{}'.format(timestamp, token),
        digestmod=hashlib.sha256
    ).hexdigest()

    return signature == expected_signature


def verify_message_reply_signature(from_user_id, to_user_id, signature):
    expected_signature = _generate_message_reply_signature(from_user_id, to_user_id)
    return signature == expected_signature


def _generate_message_reply_signature(from_user_id, to_user_id):
    return hmac.new(
        key=app.config['REPLY_TOKEN_SECRET'],
        msg='%s-%s' % (from_user_id, to_user_id),
        digestmod=hashlib.sha256
    ).hexdigest()


def _render_email(template_name, to_email, tvars):
    tvars.update(
        to_email=to_email,
        preferences_url=url_for('notifications_settings', _external=True)
    )

    text_body = render_template('emails/%s.txt' % template_name, **tvars)
    html_body = render_template('emails/%s.html' % template_name, **tvars)

    return text_body, html_body