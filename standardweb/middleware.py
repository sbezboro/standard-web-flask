import hashlib
import hmac
import os
import time
import uuid

from flask import abort, flash, g, redirect, request, session, url_for
import rollbar

from standardweb import app, stats
from standardweb.lib import csrf, geoip
from standardweb.lib import helpers as h
from standardweb.lib import player as libplayer
from standardweb.models import User, ForumBan
from standardweb.tasks.access_log import log as log_task
from sqlalchemy.orm import joinedload


@app.before_request
def user_session():
    if _is_not_static_request() and session.get('user_session_key'):
        if session.get('mfa_stage') and session['mfa_stage'] != 'mfa-verified':
            g.user = None
        else:
            g.user = User.query.options(
                joinedload(User.player)
            ).options(
                joinedload(User.posttracking)
            ).filter_by(
                session_key=session['user_session_key']
            ).first()
    else:
        g.user = None

    if not session.get('client_uuid'):
        session['client_uuid'] = uuid.uuid4()
        session.permanent = True


def _is_not_static_request():
    return request.endpoint and 'static' not in request.endpoint and request.endpoint != 'face'


@app.before_request
def force_moderator_mfa():
    if (
        _is_not_static_request() and
        request.endpoint not in ('mfa_settings', 'mfa_qr_code', 'logout') and
        g.user and
        g.user.moderator and
        not g.user.mfa_login
    ):
        flash('Moderators must use 2-factor authentication, sorry! Please enable it below', 'error')
        return redirect(url_for('mfa_settings'))


@app.before_request
def csrf_protect():
    if request.method == "POST":
        func = app.view_functions.get(request.endpoint)

        if func and func not in csrf.exempt_funcs and 'debugtoolbar' not in request.endpoint:
            session_token = session.get('csrf_token')
            request_token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')

            if not session_token or session_token != request_token:
                rollbar.report_message('CSRF mismatch', request=request, extra_data={
                    'session_token': session_token
                })

                csrf.regenerate_token()
                abort(403)


@app.before_request
def force_auth_ssl():
    # minimize MITM by making sure logged in sessions are secure after first non-secure request
    if (
        g.user and
        app.config.get('SSL_REDIRECTION') and
        not request.is_secure
    ):
        return redirect(request.url.replace('http://', 'https://'))


@app.before_request
def first_login():
    first_login = False

    if request.endpoint and 'static' not in request.endpoint \
            and request.endpoint != 'face' and session.get('user_session_key'):
        if 'first_login' in session:
            first_login = session.pop('first_login')

    g.first_login = first_login


@app.before_request
def track_request_time():
    g._start_time = time.time()


@app.before_request
def ensure_valid_user():
    if request.method == "POST" and g.user and geoip.is_nok(request.remote_addr):
        user = g.user
        player = user.player

        if not user.forum_ban:
            ban = ForumBan(user_id=g.user.id)
            ban.save(commit=True)

        if player and not player.banned:
            libplayer.ban_player(player, source='invalid_user', commit=True)


@app.after_request
def access_log(response):
    if not hasattr(g, '_start_time'):
        return response

    endpoint = request.endpoint
    route = request.url_rule.rule if request.url_rule else None

    if endpoint and (
        'static' in endpoint or endpoint == 'face'
    ):
        return response

    response_time = int(1000 * (time.time() - g._start_time))

    stats.timing('endpoints.%s.%s' % (endpoint, request.method), response_time)

    if route and route.startswith('/api'):
        return response

    client_uuid = str(session.get('client_uuid'))
    user_id = g.user.id if g.user else None

    log_task.apply_async((
        client_uuid,
        user_id,
        request.method,
        route,
        request.full_path.rstrip('?'),
        request.referrer,
        response.status_code,
        response_time,
        request.headers.get('User-Agent'),
        request.remote_addr
    ))

    return response


@app.context_processor
def inject_user():
    return dict(current_user=g.user)


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


@app.context_processor
def inject_new_notifications():
    new_notifications = 0

    if g.user:
        new_notifications = g.user.get_unread_notification_count()

    return dict(new_notifications=new_notifications)


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
        moderator = g.user.moderator

        content = '-'.join([str(user_id), username, uuid, str(int(admin)), str(int(moderator))])

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
            'is_moderator': int(moderator),
            'token': token
        }

    return {
        'rts_base_url': app.config['RTS_BASE_URL'],
        'rts_prefix': app.config['RTS_PREFIX'],
        'rts_auth_data': data
    }
