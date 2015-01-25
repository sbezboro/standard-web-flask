import hashlib
import hmac
import os
import time
import uuid

from flask import abort
from flask import g
from flask import request
from flask import session
from flask import url_for
import rollbar

from standardweb import app
from standardweb.lib import csrf
from standardweb.lib import helpers as h
from standardweb.models import User
from standardweb.tasks.access_log import log as log_task
from sqlalchemy.orm import joinedload


@app.before_request
def user_session():
    if request.endpoint and 'static' not in request.endpoint \
            and request.endpoint != 'face' and session.get('user_id'):
        
        g.user = User.query.options(
            joinedload(User.player)
        ).options(
            joinedload(User.posttracking)
        ).get(session['user_id'])
    else:
        g.user = None

    if not session.get('client_uuid'):
        session['client_uuid'] = uuid.uuid4()


@app.before_request
def csrf_protect():
    if request.method == "POST":
        func = app.view_functions.get(request.endpoint)

        if func and func not in csrf.exempt_funcs and 'debugtoolbar' not in request.endpoint:
            token = session.get('csrf_token')

            if not token or token != request.form.get('csrf_token'):
                rollbar.report_message('CSRF mismatch', request=request, extra_data={
                    'session_token': token
                })

                csrf.regenerate_token()
                abort(403)


@app.before_request
def first_login():
    first_login = False

    if request.endpoint and 'static' not in request.endpoint \
            and request.endpoint != 'face' and session.get('user_id'):
        if 'first_login' in session:
            first_login = session.pop('first_login')

    g.first_login = first_login


@app.before_request
def track_request_time():
    g._start_time = time.time()


@app.after_request
def access_log(response):
    if (
        request.endpoint and (
            'static' in request.endpoint
            or request.endpoint == 'face'
        )
    ):
        return response

    client_uuid = session.get('client_uuid')
    user_id = g.user.id if g.user else None
    route = request.url_rule.rule if request.url_rule else None
    request_time = int(1000 * (time.time() - g._start_time))

    log_task.apply_async((
        client_uuid,
        user_id,
        request.method,
        route,
        request.path,
        response.status_code,
        request_time,
        request.headers.get('User-Agent'),
        request.remote_addr
    ))

    return response


@app.context_processor
def inject_user():
    return dict(user=g.user)


@app.context_processor
def inject_h():
    return dict(h=h)


@app.context_processor
def inject_debug():
    return dict(is_debug=app.config['DEBUG'])


@app.context_processor
def inject_cdn_domain():
    if not app.config['DEBUG']:
        cdn_domain = '//%s' % app.config['CDN_DOMAIN']
    else:
        cdn_domain = ''

    return dict(cdn_domain=cdn_domain)


@app.context_processor
def inject_new_messages():
    new_messages = 0

    if g.user:
        new_messages = g.user.get_unread_message_count()

    return dict(new_messages=new_messages)


def _dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)

        if filename:
            file_path = os.path.join(app.root_path, endpoint, filename)
            try:
                values['t'] = int(os.stat(file_path).st_mtime)
            except:
                pass

    return url_for(endpoint, **values)


@app.context_processor
def rts_auth_data():
    data = {}

    if g.user:
        user_id = g.user.id
        username = g.user.player.username if g.user.player else g.user.username
        uuid = g.user.player.uuid if g.user.player else ''
        admin = g.user.admin

        content = '-'.join([str(user_id), username, uuid, str(int(admin))])

        token = hmac.new(
            app.config['RTS_SECRET'],
            msg=content,
            digestmod=hashlib.sha256
        ).hexdigest()

        data = {
            'user_id': user_id,
            'username': username,
            'uuid': uuid,
            'is_superuser': int(admin),
            'token': token
        }

    return {
        'rts_base_url': app.config['RTS_BASE_URL'],
        'rts_prefix': app.config['RTS_PREFIX'],
        'rts_auth_data': data
    }
