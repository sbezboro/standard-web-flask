from datetime import datetime
import pytz

from flask import (
    g,
    jsonify,
    render_template,
    request
)
import rollbar
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from standardweb import app, db, stats
from standardweb.lib import forums as libforums
from standardweb.lib import messages as libmessages
from standardweb.lib import player as libplayer
from standardweb.lib import realtime
from standardweb.lib.notifier import notify_new_message, notify_message_read
from standardweb.models import ForumBan, Message, Player, User
from standardweb.views.decorators.auth import login_required


@app.route('/messages')
@app.route('/messages/<username>')
@app.route('/messages/<path:path>')
@login_required()
def messages(username=None, path=None):
    return render_template('messages/index.html')


@app.route('/messages/contacts.json')
@login_required()
def contacts_json():
    user = g.user

    all_messages = Message.query.filter(
        or_(Message.from_user == user, Message.to_user == user),
        Message.deleted == False
    ).options(
        joinedload(Message.from_user)
        .joinedload(User.player)
    ).options(
        joinedload(Message.to_user)
        .joinedload(User.player)
    ).options(
        joinedload(Message.to_player)
    ).order_by(
        Message.sent_at.desc()
    ).all()

    contacts = []
    seen_usernames = set()

    for message in all_messages:
        from_username = message.from_user.get_username()
        to_username = message.to_user.get_username() if message.to_user else message.to_player.username

        contact = None

        if from_username not in seen_usernames and message.from_user != user:
            contact = {
                'user': message.from_user.to_dict(),
                'username': from_username,
                'last_message_id': message.id,
                'last_message_date': message.sent_at.replace(tzinfo=pytz.UTC).isoformat(),
                'new_message': not message.seen_at
            }

            if message.from_user.player:
                contact['player'] = message.from_user.player.to_dict()

            seen_usernames.add(from_username)
        elif to_username not in seen_usernames and message.to_user != user:
            contact = {
                'username': to_username,
                'last_message_id': message.id,
                'last_message_date': message.sent_at.replace(tzinfo=pytz.UTC).isoformat(),
                'new_message': False
            }

            if message.to_user:
                contact['user'] = message.to_user.to_dict()
            if message.to_player:
                contact['player'] = message.to_player.to_dict()

            seen_usernames.add(to_username)

        if contact:
            contacts.append(contact)

    return jsonify({
        'err': 0,
        'contacts': contacts
    })


@app.route('/messages/<username>.json')
@login_required()
def messages_json(username):
    user = g.user

    to_user = User.query.outerjoin(Player).options(
        joinedload(User.player)
    ).filter(
        or_(Player.username == username, User.username == username)
    ).first()

    if to_user == user:
        # don't allow user to send messages to themselves
        return jsonify({
            'err': 1
        })

    if to_user:
        to_player = to_user.player
    else:
        # for cases of messages sent to players with no users created yet
        to_player = Player.query.filter_by(username=username).first()

        if not to_player:
            rollbar.report_message('to_player None', request=request)
            return jsonify({
                'err': 1
            })

    if to_user:
        # If the username matches an existing user, use it for the message query
        recipient_filter = or_(
            and_(Message.from_user == user, Message.to_user == to_user),
            and_(Message.from_user == to_user, Message.to_user == user)
        )
    else:
        # Otherwise, use the player matched by the username for the message query
        recipient_filter = or_(
            and_(Message.from_user == user, Message.to_player == to_player),
            and_(Message.from_user == to_user, Message.to_user == user)
        )

    messages = Message.query.filter(
        recipient_filter,
        Message.deleted == False
    ).options(
        joinedload(Message.from_user)
        .joinedload(User.player)
    ).options(
        joinedload(Message.to_user)
        .joinedload(User.player)
    ).options(
        joinedload(Message.to_player)
    ).order_by(
        Message.sent_at.desc()
    ).limit(200).all()

    Message.query.filter(
        recipient_filter,
        Message.to_user == user,
        Message.seen_at.is_(None)
    ).update({
        'seen_at': datetime.utcnow()
    })

    db.session.commit()

    for message in messages:
        if message.to_user == user and not message.seen_at:
            notify_message_read(message)

    realtime.unread_message_count(user)

    messages = map(lambda x: x.to_dict(), messages)

    return jsonify({
        'err': 0,
        'username': username,
        'messages': messages
    })


@app.route('/messages/<username>/new', methods=['POST'])
@login_required()
def send_message(username):
    user = g.user
    player = user.player

    if user.forum_ban or (player and player.banned):
        rollbar.report_message('User blocked from sending a message', level='warning', request=request)
        return jsonify({
            'err': 1,
            'message': 'Oops, you are blocked from sending any messages. Awkward...'
        })

    body = request.form.get('body')

    to_user = User.query.outerjoin(Player).options(
        joinedload(User.player)
    ).filter(
        or_(Player.username == username, User.username == username)
    ).first()

    if to_user:
        to_player = to_user.player
    else:
        # for cases of messages sent to players with no users created yet
        to_player = Player.query.filter_by(username=username).first()

        if not to_player:
            rollbar.report_message('to_player None', request=request)
            return jsonify({
                'err': 1
            })

    if libmessages.is_sender_spamming(user, to_user, to_player):
        can_post = libforums.can_user_post(user)

        rollbar.report_message('User blocked from spamming messages', request=request, extra_data={
            'to_user_id': to_user.id if to_user else None,
            'to_player_id': to_player.id if to_player else None,
            'can-Post': can_post
        })

        if not can_post and not user.forum_ban:
            player = user.player
            libplayer.ban_player(player, source='message_spamming', commit=False)

            ban = ForumBan(user_id=user.id)
            ban.save(commit=True)

        return jsonify({
            'err': 1,
            'message': 'Whoa there, you sent too many messages recently! Try sending a bit later.'
        })

    message = Message(
        from_user=user,
        to_user=to_user,
        to_player=to_player,
        body=body,
        user_ip=request.remote_addr
    )

    message.save()

    notify_new_message(message)

    stats.incr('messages.created')

    return jsonify({
        'err': 0,
        'message': message.to_dict()
    })


@app.route('/messages/mark_read', methods=['POST'])
@login_required()
def read_message():
    user = g.user

    if not user:
        return jsonify({
            'err': 1,
            'message': 'Must be logged in'
        })

    username = request.form.get('username')

    from_user = User.query.outerjoin(Player).filter(
        or_(
            User.username == username,
            Player.username == username
        )
    ).first()

    if not from_user:
        return jsonify({
            'err': 1,
            'message': 'Username not found'
        })

    messages = Message.query.filter_by(
        from_user_id=from_user.id,
        to_user=user,
        seen_at=None
    )

    now = datetime.utcnow()

    for message in messages:
        message.seen_at = now
        message.save(commit=False)

        notify_message_read(message)

    db.session.commit()

    realtime.unread_message_count(user)

    return jsonify({
        'err': 0
    })
