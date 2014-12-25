from flask import render_template
from flask import url_for
from standardweb.lib import notifications

from standardweb.models import EmailToken
from standardweb.tasks import send_email as send_email_task


DEFAULT_FROM_EMAIL = 'Standard Survival <server@standardsurvival.com>'
EMAIL_URL = 'https://api.mailgun.net/v2/standardsurvival.com/messages'


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


def send_new_message_email(user, message):
    if not _verify_email_preference(user, 'new_message'):
        return

    from_user = message.from_user
    from_username = message.from_user.get_username()

    conversation_url = url_for('messages', username=from_username, _external=True)

    from_player_url = None
    if from_user.player:
        from_player_url = url_for('player', username=from_username, _external=True)

    to_email = user.email

    unsubscribe_link = notifications.generate_unsubscribe_link(user, 'new_message')

    text_body, html_body = _render_email('messages/new_message', to_email, {
        'username': user.get_username(),
        'from_username': from_username,
        'message_body': message.body,
        'message_body_html': message.body_html,
        'conversation_url': conversation_url,
        'from_player_url': from_player_url,
        'unsubscribe_url': unsubscribe_link
    })

    send_email(to_email, '[Standard Survival] New message from %s' % from_username, text_body, html_body)


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


def _verify_email_preference(user, type):
    return user.get_notification_preference(type).email


def _render_email(template_name, to_email, tvars):
    tvars.update(
        to_email=to_email,
        preferences_url=url_for('notifications_settings', _external=True)
    )

    text_body = render_template('emails/%s.txt' % template_name, **tvars)
    html_body = render_template('emails/%s.html' % template_name, **tvars)

    return text_body, html_body
