from standardweb.lib import csrf

from flask import request

from flask_wtf import Form
from wtforms import HiddenField, PasswordField, TextField
from wtforms.validators import DataRequired

from urlparse import urljoin
from urlparse import urlparse


def _is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))

    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


def _get_redirect_target():
    for target in request.args.get('next'), request.referrer:
        if not target:
            continue

        if _is_safe_url(target):
            return target

    return ''


class BaseForm(Form):
    csrf_token = HiddenField()

    def __init__(self, *args, **kwargs):
        super(BaseForm, self).__init__(*args, **kwargs)

        if not self.csrf_token.data:
            self.csrf_token.data = csrf.get_token()


# inspired by http://flask.pocoo.org/snippets/63/
class RedirectForm(BaseForm):
    next = HiddenField()

    def __init__(self, *args, **kwargs):
        super(RedirectForm, self).__init__(*args, **kwargs)

        if not self.next.data:
            self.next.data = _get_redirect_target()


class LoginForm(RedirectForm):
    username = TextField('Minecraft Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
