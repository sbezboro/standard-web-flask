import requests
import rollbar

from flask import render_template
from flask import request
from flask import url_for

from standardweb import app
from standardweb.models import EmailToken


DEFAULT_FROM_EMAIL = 'Standard Survival <server@standardsurvival.com>'
EMAIL_URL = 'https://api.mailgun.net/v2/standardsurvival.com/messages'


def send_creation_email(to_email, uuid, username):
    email_token = EmailToken.create_creation_token(to_email, uuid, commit=False)

    verify_url = url_for('create_account', token=email_token.token, _external=True)

    text_body, html_body = _render_email('create_account', {
        'username': username,
        'verify_url': verify_url
    })

    email_token.save(commit=True)

    return send_email(to_email, '[Standard Survival] Please verify your email', text_body, html_body)


def send_verify_email(to_email, user):
    email_token = EmailToken.create_verify_token(to_email, user.id, commit=False)

    verify_url = url_for('verify_email', token=email_token.token, _external=True)

    text_body, html_body = _render_email('verify_email', {
        'username': user.player.username,
        'verify_url': verify_url
    })

    email_token.save(commit=True)

    return send_email(to_email, '[Standard Survival] Please verify your email', text_body, html_body)


def send_reset_password(user):
    email_token = EmailToken.create_reset_password_token(user.id, commit=False)

    verify_url = url_for('reset_password', token=email_token.token, _external=True)

    text_body, html_body = _render_email('reset_password', {
        'verify_url': verify_url
    })

    email_token.save(commit=True)

    return send_email(user.email, '[Standard Survival] Reset password', text_body, html_body)


def send_new_message_email(user, message):
    from_user = message.from_user
    from_username = message.from_user.get_username()

    from_email = None
    if from_user.email:
        from_email = '%s <%s>' % (from_username, from_user.email)

    conversation_url = url_for('messages', username=from_username, _external=True)

    from_player_url = None
    if from_user.player:
        from_player_url = url_for('player', username=from_username, _external=True)

    text_body, html_body = _render_email('messages/new_message', {
        'username': user.get_username(),
        'from_username': from_username,
        'message_body': message.body,
        'message_body_html': message.body_html,
        'conversation_url': conversation_url,
        'from_player_url': from_player_url
    })

    return send_email(user.email, '[Standard Survival] New message from %s' % from_username, text_body, html_body)


def send_email(to_email, subject, text_body, html_body, from_email=None):
    if not to_email:
        return None

    return _send_email(from_email or DEFAULT_FROM_EMAIL, to_email, subject, text_body, html_body)


def _send_email(from_email, to_emails, subject, text_body, html_body):
    auth = ('api', app.config['MAILGUN_API_KEY'])

    data = {
        'from': from_email,
        'to': to_emails,
        'subject': subject,
        'text': text_body,
        'html': html_body
    }

    result = None

    try:
        result = requests.post(EMAIL_URL, auth=auth, data=data)
    except:
        rollbar.report_exc_info(request=request)
    else:
        if result.status_code == 200:
            rollbar.report_message('Email sent', level='info', request=request, extra_data={
                'data': data,
                'result': result.json()
            })
        else:
            rollbar.report_message('Problem sending email', level='error', request=result, extra_data={
                'data': data,
                'result': result
            })

    return result


def _render_email(template_name, tvars):
    text_body = render_template('emails/%s.txt' % template_name, **tvars)
    html_body = render_template('emails/%s.html' % template_name, **tvars)

    return text_body, html_body
