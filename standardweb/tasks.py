from flask import json

import requests
import rollbar

from standardweb import app
from standardweb import celery


@celery.task()
def send_email(from_email, to_emails, subject, text_body, html_body):
    from standardweb.lib.email import EMAIL_URL

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
    except Exception:
        rollbar.report_exc_info()
    else:
        if result.status_code == 200:
            rollbar.report_message('Email sent', level='info', extra_data={
                'data': data,
                'result': result.json()
            })
        else:
            rollbar.report_message('Problem sending email', level='error', extra_data={
                'data': data,
                'result': result
            })

    return result


@celery.task()
def send_rts_data(user_id, channel, action, payload):
    url = '%s%s/%s' % (app.config['RTS_BASE_URL'], app.config['RTS_PREFIX'], channel)

    headers = {
        'X-Standard-Secret': app.config['RTS_SECRET'],
        'Content-Type': 'application/json'
    }

    data = {
        'user_id': user_id,
        'action': action,
        'payload': payload
    }

    result = None

    try:
        result = requests.post(url, data=json.dumps(data), headers=headers)
    except Exception:
        rollbar.report_exc_info()

    return result