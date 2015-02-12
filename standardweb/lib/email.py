import base64
from functools import wraps
import hashlib
import hmac

from flask import render_template
from flask import url_for
from sqlalchemy.orm import joinedload

from standardweb import app
from standardweb.lib import notifications
from standardweb.models import EmailToken, User, ForumPost
from standardweb.tasks.email import send_email as send_email_task


DEFAULT_FROM_EMAIL = 'Standard Survival <server@standardsurvival.com>'
MESSAGE_REPLY_FROM_EMAIL = 'Standard Survival <message-reply@mail.standardsurvival.com>'
EMAIL_URL = 'https://api.mailgun.net/v2/mail.standardsurvival.com/messages'

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
        from_player_url = url_for('player', username=from_username, _external=True)

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

    forum_topic_url = url_for('forum_topic', topic_id=post.topic_id, _external=True)
    unsubscribe_link = notifications.generate_unsubscribe_link(user, 'news')

    text_body, html_body = _render_email('news_post', to_email, {
        'post_body': post.id,
        'post_body_html': post.body_html,
        'topic_url': forum_topic_url,
        'unsubscribe_url': unsubscribe_link
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
    ).get(post_id)

    topic = post.topic

    forum_post_url = url_for('forum_post', post_id=post_id, _external=True)
    unsubscribe_topic_url = url_for('forum_topic_unsubscribe', topic_id=topic.id, _external=True)
    unsubscribe_url = notifications.generate_unsubscribe_link(user, 'subscribed_thread_post')

    text_body, html_body = _render_email('subscribed_topic_post', to_email, {
        'username': user.get_username(),
        'post_body': post.body,
        'post_body_html': post.body_html,
        'post_url': forum_post_url,
        'unsubscribe_topic_url': unsubscribe_topic_url,
        'unsubscribe_url': unsubscribe_url
    })

    send_email(to_email, '[Standard Survival] New reply in the topic "%s"' % topic.name, text_body, html_body)


def send_notification_email(user, notification):
    func = NOTIFICATION_EMAILS[notification.type]

    if func:
        func(user, notification)


def send_email(to_email, subject, text_body, html_body, from_email=None):
    if not to_email:
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