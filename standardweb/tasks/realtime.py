from flask import json
import requests
import rollbar

from standardweb import app
from standardweb import celery


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