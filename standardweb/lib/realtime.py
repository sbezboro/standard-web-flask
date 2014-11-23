import pytz

from flask import json, render_template, request

import requests
import rollbar

from standardweb import app


def new_message(user, message):
    message_row_html = render_template(
        'messages/includes/message_row.html',
        user=user,
        message=message
    )

    payload = {
        'date': message.sent_at.replace(tzinfo=pytz.UTC).isoformat(),
        'message_row_html': message_row_html,
        'from_user_id': message.from_user_id
    }

    send_rts_data(message.to_user_id, 'messages', 'new', payload)


def unread_message_count(user):
    payload = {
        'count': user.get_unread_message_count()
    }

    send_rts_data(user.id, 'messages', 'unread-count', payload)


def send_rts_data(user_id, channel, action, payload):
    url = '%s/%s' % (app.config['RTS_ADDRESS'], channel)

    headers = {
        'X-Standard-Secret': app.config['RTS_SECRET'],
        'Content-Type': 'application/json'
    }

    data = {
        'user_id': user_id,
        'action': action,
        'payload': payload
    }

    try:
        return requests.post(url, data=json.dumps(data), headers=headers, timeout=2)
    except Exception:
        rollbar.report_exc_info(request=request)
        return None
