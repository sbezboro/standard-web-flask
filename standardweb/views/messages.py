from datetime import datetime, timedelta
import pytz

from flask import (
    abort,
    after_this_request,
    flash,
    g,
    jsonify,
    render_template,
    request,
    url_for
)
from markupsafe import Markup
import rollbar
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from standardweb import app, db, stats
from standardweb.lib import realtime
from standardweb.lib.notifier import notify_new_message
from standardweb.models import User, Player, Message
from standardweb.views.decorators.auth import login_required


MESSAGE_THROTTLE_COUNT = 60
MESSAGE_THROTTLE_PERIOD = 60  # minutes


@app.route('/messages')
@app.route('/messages/<username>')
@app.route('/messages/<path:path>')
@login_required()
def messages(username=None, path=None):
    user = g.user

    if not user.email:
        flash(Markup(
            '<a href="%s">Set an email address</a> to receive email notifications for new messages!'
            % url_for('profile_settings')
        ), 'warning')

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
    ).limit(40).all()

    for message in messages:
        if message.to_user == user and not message.seen_at:
            Message.query.filter_by(
                to_user=user,
                from_user=message.from_user,
                seen_at=None
            ).update({
                'seen_at': datetime.utcnow()
            })

            @after_this_request
            def commit(response):
                db.session.commit()
                realtime.unread_message_count(user)
                return response

            break

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

    if user.forum_ban:
        abort(403)

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

    # prevent spam
    recent_messages = Message.query.with_entities(Message.id).filter(
        Message.from_user == user,
        Message.sent_at > datetime.utcnow() - timedelta(minutes=MESSAGE_THROTTLE_PERIOD),
        Message.deleted == False
    ).all()

    if not app.config['DEBUG'] and len(recent_messages) > MESSAGE_THROTTLE_COUNT:
        # TODO: handle auto alerting for ajax requests
        return jsonify({
            'err': 1,
            'message': 'Whoa there, you sent too many messages recently! Try sending a bit later.'
        })
    else:
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

    from_user = User.query.join(Player).filter(
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

    Message.query.filter_by(
        from_user_id=from_user.id,
        to_user=user,
        seen_at=None
    ).update({
        'seen_at': datetime.utcnow()
    })

    db.session.commit()

    realtime.unread_message_count(user)

    return jsonify({
        'err': 0
    })
