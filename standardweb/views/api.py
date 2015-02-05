import base64
from datetime import datetime
from functools import wraps
import re

from flask import abort
from flask import g
from flask import jsonify
from flask import request
from flask import url_for
import rollbar

from sqlalchemy import or_
from sqlalchemy.sql.expression import func
from sqlalchemy.orm import joinedload

from standardweb import app, db
from standardweb.lib import helpers as h
from standardweb.lib import player as libplayer
from standardweb.lib import realtime
from standardweb.lib.csrf import exempt_funcs
from standardweb.lib.email import (
    send_creation_email,
    send_verify_email,
    verify_mailgun_signature,
    verify_message_reply_signature
)
from standardweb.lib.notifier import notify_new_message
from standardweb.models import (
    Server, Player, DeathType, DeathEvent, KillCount, KillEvent, KillType, MaterialType,
    OreDiscoveryEvent, OreDiscoveryCount, EmailToken, User, PlayerStats, VeteranStatus, Message,
    Title, AuditLog, DeathCount
)


# Base API function decorator that auto creates url rules for API endpoints.
def api_func(function):

    @wraps(function)
    def decorator(*args, **kwargs):
        version = int(kwargs['version'])
        if version < 1 or version > 1:
            abort(404)
        
        del kwargs['version']
        return function(*args, **kwargs)

    exempt_funcs.add(decorator)

    name = function.__name__
    app.add_url_rule('/api/v<int:version>/%s' % name, name, decorator, methods=['GET', 'POST'])
    
    return decorator


# API function decorator for any api operation exposed to a Minecraft server.
# This access must be authorized by server-id/secret-key pair combination.
def server_api(function):

    @wraps(function)
    def decorator(*args, **kwargs):
        server = None

        if request.headers.get('Authorization'):
            auth = request.headers['Authorization'].split(' ')[1]
            server_id, secret_key = auth.strip().decode('base64').split(':')

            server = Server.query.filter_by(id=server_id, secret_key=secret_key).first()

        if not server:
            abort(403)

        setattr(g, 'server', server)
        
        return function(*args, **kwargs)

    api_func(decorator)
    
    return decorator


@server_api
def log_death():
    type = request.form.get('type')
    victim_uuid = request.form.get('victim_uuid')
    killer_uuid = request.form.get('killer_uuid')

    victim = Player.query.filter_by(uuid=victim_uuid).first()

    if victim_uuid == killer_uuid:
        type = 'suicide'

    death_type = DeathType.factory(type=type)

    if type == 'player':
        killer = Player.query.filter_by(uuid=killer_uuid).first()

        death_event = DeathEvent(server=g.server, death_type=death_type, victim=victim, killer=killer)
        DeathCount.increment(g.server, death_type, victim, killer, commit=False)
    else:
        death_event = DeathEvent(server=g.server, death_type=death_type, victim=victim)
        DeathCount.increment(g.server, death_type, victim, None, commit=False)

    death_event.save(commit=True)

    return jsonify({
        'err': 0
    })


@server_api
def log_kill():
    type = request.form.get('type')
    killer_uuid = request.form.get('killer_uuid')

    killer = Player.query.filter_by(uuid=killer_uuid).first()
    if not killer:
        return jsonify({
            'err': 1
        })

    kill_type = KillType.factory(type=type)

    kill_event = KillEvent(server=g.server, kill_type=kill_type, killer=killer)
    KillCount.increment(g.server, kill_type, killer, commit=False)

    kill_event.save(commit=True)

    return jsonify({
        'err': 0
    })


@server_api
def log_ore_discovery():
    uuid = request.form.get('uuid')
    type = request.form.get('type')
    x = int(request.form.get('x'))
    y = int(request.form.get('y'))
    z = int(request.form.get('z'))

    player = Player.query.filter_by(uuid=uuid).first()

    if not player:
        return jsonify({
            'err': 1
        })

    material_type = MaterialType.factory(type=type)

    ore_event = OreDiscoveryEvent(server=g.server, material_type=material_type,
                                  player=player, x=x, y=y, z=z)
    OreDiscoveryCount.increment(g.server, material_type, player, commit=False)

    ore_event.save(commit=True)

    return jsonify({
        'err': 0
    })


@server_api
def register():
    uuid = request.form.get('uuid')
    email = request.form.get('email')
    username = request.form.get('username')

    player = Player.query.filter_by(uuid=uuid).first()
    if not player:
        return jsonify({
            'err': 1,
            'message': 'Please try again later'
        })

    user = User.query.filter_by(player=player).first()
    if user and user.email:
        return jsonify({
            'err': 1,
            'message': 'You are already registered!'
        })

    if not h.is_valid_email(email):
        return jsonify({
            'err': 1,
            'message': 'Not a valid email address'
        })

    other_user = User.query.filter_by(email=email).first()
    if other_user:
        return jsonify({
            'err': 1,
            'message': 'Email already in use'
        })

    email_tokens = EmailToken.query.filter_by(uuid=uuid)
    for email_token in email_tokens:
        db.session.delete(email_token)

    # old-style user without an email, just let them verify an email
    if user:
        send_verify_email(email, user)
    else:
        send_creation_email(email, uuid, username)

    return jsonify({
        'err': 0,
        'message': 'Email sent! Check your inbox for further instructions'
    })


@server_api
def rank_query():
    username = request.args.get('username')
    uuid = request.args.get('uuid')

    if uuid:
        player = Player.query.options(
            joinedload(Player.titles)
        ).filter_by(uuid=uuid).first()
    else:
        player = Player.query.options(
                joinedload(Player.titles)
            ).filter(or_(Player.username.ilike('%%%s%%' % username),
                                         Player.nickname.ilike('%%%s%%' % username)))\
            .order_by(func.ifnull(Player.nickname, Player.username))\
            .limit(1).first()

    if not player:
        return jsonify({
            'err': 1
        })

    stats = PlayerStats.query.filter_by(server=g.server, player=player).first()

    if not stats:
        return jsonify({
            'err': 1
        })

    time = h.elapsed_time_string(stats.time_spent)

    veteran_statuses = VeteranStatus.query.filter_by(player=player)
    for veteran_status in veteran_statuses:
        server_id = veteran_status.server_id
        rank = veteran_status.rank

        server_name = {
            1: 'SS I',
            2: 'SS II',
            4: 'SS III'
        }[server_id]

        if rank <= 10:
            veteran_group = 'Top 10 Veteran'
        elif rank <= 40:
            veteran_group = 'Top 40 Veteran'
        else:
            veteran_group = 'Veteran'

        title_name = '%s %s' % (server_name, veteran_group)
        title = Title.query.filter_by(name=title_name).first()

        if title and title not in player.titles:
            player.titles.append(title)
            player.save(commit=True)

    titles = [{'name': x.name, 'broadcast': x.broadcast} for x in player.titles]

    retval = {
        'err': 0,
        'rank': stats.rank,
        'time': time,
        'minutes': stats.time_spent,
        'username': player.username,
        'uuid': player.uuid,
        'titles': titles
    }

    return jsonify(retval)


@server_api
def join_server():
    url = url_for('messages', _external=True)
    uuid = request.form.get('uuid')

    player = Player.query.filter_by(uuid=uuid).first()

    num_new_messages = 0
    from_uuids = set()
    no_user = True
    past_usernames = set()

    if player:
        no_user = not player.user

        messages = Message.query.options(
            joinedload(Message.from_user)
            .joinedload(User.player)
        ).filter_by(
            to_player=player,
            seen_at=None
        )

        for message in messages:
            player = message.from_user.player
            if player:
                from_uuids.add(player.uuid)

            num_new_messages += 1

        past_username_logs = AuditLog.query.filter_by(
            player=player,
            type='player_rename'
        ).order_by(
            AuditLog.timestamp
        )

        for log in past_username_logs:
            past_username = log.data['old_name']
            past_usernames.add(past_username)

    return jsonify({
        'err': 0,
        'player_messages': {
            'num_new_messages': num_new_messages,
            'from_uuids': list(from_uuids),
            'url': url
        },
        'no_user': no_user,
        'past_usernames': list(past_usernames)
    })


@server_api
def leave_server():
    username = request.form.get('username')

    player = Player.query.filter_by(username=username).first()

    if player:
        player_stats = PlayerStats.query.filter_by(server=g.server, player=player).first()

        if player_stats:
            player_stats.last_seen = datetime.utcnow()
            player_stats.save(commit=True)

    return jsonify({
        'err': 0
    })


@server_api
def audit_log():
    body = request.json

    type = body.get('type')
    data = body.get('data')
    uuid = body.get('uuid')

    if not type:
        return jsonify({
            'err': 1,
            'message': 'Missing type'
        }), 400

    player_id = None

    if uuid:
        player = Player.query.filter_by(uuid=uuid).first()
        if player:
            player_id = player.id

    AuditLog.create(
        type,
        data=data,
        server_id=g.server.id,
        player_id=player_id,
        commit=True
    )

    return jsonify({
        'err': 0
    })


@api_func
def servers():
    servers = [{
        'id': server.id,
        'address': server.address,
        'online': server.online
    } for server in Server.query.all()]

    return jsonify({
        'err': 0,
        'servers': servers
    })


@api_func
def contact_query():
    query = request.args.get('query')

    contacts = []

    if query:
        players = libplayer.filter_players(query, page_size=10)

        contacts = [{
            'player_id': player.id,
            'username': player.username,
            'nickname': player.nickname,
            'displayname_html': player.displayname_html
        } for player in players]

        users = User.query.filter(
            User.username.ilike('%%%s%%' % query)
        ).order_by(
            User.username.desc()
        )

        for user in users:
            contacts.insert(0, {
                'user_id': user.id,
                'username': user.username,
                'nickname': None,
                'displayname_html': user.username
            })

    return jsonify({
        'err': 0,
        'contacts': contacts
    })

@api_func
def mark_messages_read():
    user = g.user
    if not user:
        return jsonify({
            'err': 1,
            'message': 'Must be logged in'
        })

    other_user_id = request.form.get('other_user_id')

    Message.query.filter_by(
        from_user_id=other_user_id,
        to_user=user
    ).update({
        'seen_at': datetime.utcnow()
    })

    db.session.commit()

    realtime.unread_message_count(user)

    return jsonify({
        'err': 0
    })


@api_func
def message_reply():
    api_key = app.config['MAILGUN_API_KEY']

    token = request.form.get('token')
    timestamp = request.form.get('timestamp')
    signature = request.form.get('signature')

    if not verify_mailgun_signature(api_key, token, timestamp, signature):
        abort(403)

    body = request.form.get('stripped-text')
    full_body = request.form.get('body-plain')
    sender = request.form.get('sender')

    # try to find the reply token of the original message
    match = re.search(r'--([^\s]+)-([^\s]+)-([^\s]+)--', full_body)

    if match:
        b64_from_user_id, b64_to_user_id, signature = match.groups()

        try:
            # swap to/from in the original message since this is a reply
            reply_to_user_id = base64.b64decode(b64_from_user_id)
            reply_from_user_id = base64.b64decode(b64_to_user_id)
        except Exception:
            rollbar.report_message('Message not sent via email - cannot parse token', level='warning', extra_data={
                'b64_from_user_id': b64_from_user_id,
                'b64_to_user_id': b64_to_user_id
            })
        else:
            if verify_message_reply_signature(reply_to_user_id, reply_from_user_id, signature):
                to_user = User.query.options(
                    joinedload(User.player)
                ).get(reply_to_user_id)
                from_user = User.query.options(
                    joinedload(User.player)
                ).get(reply_from_user_id)

                if to_user and from_user:
                    message = Message(
                        from_user=from_user,
                        to_user=to_user,
                        to_player=to_user.player,
                        body=body,
                        user_ip=request.remote_addr
                    )
                    message.save()

                    notify_new_message(message)

                    rollbar.report_message('Message successfully sent via email', level='debug', extra_data={
                        'from_user_id': from_user.id,
                        'to_user_id': to_user.id
                    })
                else:
                    rollbar.report_message('Message not sent via email - user not found', level='warning', extra_data={
                        'reply_from_user_id': reply_from_user_id,
                        'reply_to_user_id': reply_to_user_id
                    })
            else:
                rollbar.report_message('Message not sent via email - reply token signature mismatch', level='warning', extra_data={
                    'reply_from_user_id': reply_from_user_id,
                    'reply_to_user_id': reply_to_user_id,
                    'signature': signature
                })
    else:
        rollbar.report_message('Message not sent via email - token not found', level='warning', extra_data={
            'sender': sender,
            'full_body': full_body
        })

    return jsonify({})
