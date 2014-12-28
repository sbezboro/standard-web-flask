import hashlib
import hmac
import urllib

from flask import url_for

from standardweb import app


def _generate_signature(encoded_email, type):
    return hmac.new(
        app.config['UNSUBSCRIBE_SECRET'],
        msg='%s/%s' % (encoded_email, type),
        digestmod=hashlib.sha256
    ).hexdigest()


def verify_unsubscribe_request(encoded_email, type, signature):
    expected_signature = _generate_signature(encoded_email, type)

    return signature == expected_signature


def generate_unsubscribe_link(user, type):
    encoded_email = urllib.quote(user.email)
    signature = _generate_signature(encoded_email, type)

    return url_for('unsubscribe', encoded_email=encoded_email, type=type, signature=signature, _external=True)
