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

    tvars = {
        'username': username,
        'verify_url': verify_url
    }

    body = render_template('emails/create_account.html', **tvars)

    email_token.save(commit=True)

    send_email(to_email, '[Standard Survival] Please verify your email', body)



def send_verify_email(to_email, user):
    email_token = EmailToken.create_verify_token(to_email, user.id, commit=False)

    verify_url = url_for('verify_email', token=email_token.token, _external=True)

    tvars = {
        'username': user.player.username,
        'verify_url': verify_url
    }

    body = render_template('emails/verify_email.html', **tvars)

    email_token.save(commit=True)

    send_email(to_email, '[Standard Survival] Please verify your email', body)


def send_reset_password(user):
    email_token = EmailToken.create_reset_password_token(user.id, commit=False)

    verify_url = url_for('reset_password', token=email_token.token, _external=True)

    tvars = {
        'verify_url': verify_url
    }

    body = render_template('emails/reset_password.html', **tvars)

    email_token.save(commit=True)

    send_email(user.email, '[Standard Survival] Reset password', body)


def send_email(to_email, subject, body_html, from_email=None):
    return _send_email(from_email or DEFAULT_FROM_EMAIL, to_email, subject, body_html)


def _send_email(from_email, to_emails, subject, body_html):
    auth = ('api', app.config['MAILGUN_API_KEY'])

    data = {
        'from': from_email,
        'to': to_emails,
        'subject': subject,
        'html': body_html
    }

    try:
        result = requests.post(EMAIL_URL, auth=auth, data=data)
    except:
        rollbar.report_exc_info(request=request)
    else:
        rollbar.report_message('Email sent', level='info', request=request, extra_data={
            'data': data,
            'result': result.json()
        })
