from datetime import datetime, timedelta

from flask import (
    abort,
    after_this_request,
    flash,
    g,
    jsonify,
    render_template,
    redirect,
    request,
    url_for
)
from markupsafe import Markup
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from standardweb import app, db
from standardweb.forms import MessageForm
from standardweb.lib import realtime
from standardweb.lib.notifier import notify_new_message
from standardweb.models import User, Player, Message
from standardweb.views.decorators.auth import login_required


MESSAGE_THROTTLE_COUNT = 60
MESSAGE_THROTTLE_PERIOD = 60  # minutes


@app.route('/messages')
@app.route('/messages/<username>', methods=['GET', 'POST'])
@login_required()
def messages(username=None):
    user = g.user

    messages = []
    form = MessageForm()

    template_vars = {
        'form': form
    }

    other_user_id = None

    if username:
        to_user = User.query.outerjoin(Player).options(
            joinedload(User.player)
        ).filter(
            or_(Player.username == username, User.username == username)
        ).first()

        if to_user == user:
            # don't allow user to send messages to themselves
            return redirect(url_for('messages'))

        if to_user:
            other_user_id = to_user.id
            to_player = to_user.player
        else:
            # for cases of messages sent to players with no users created yet
            to_player = Player.query.filter_by(username=username).first()

            if not to_player:
                abort(404)

        if form.validate_on_submit():
            text = form.text.data

            # prevent spam
            recent_messages = Message.query.with_entities(Message.id).filter(
                Message.from_user == user,
                Message.sent_at > datetime.utcnow() - timedelta(minutes=MESSAGE_THROTTLE_PERIOD)
            ).all()

            if not app.config['DEBUG'] and len(recent_messages) > MESSAGE_THROTTLE_COUNT:
                flash('Whoa there, you sent too many messages recently! Try sending a bit later.', 'error')
            else:
                message = Message(from_user=user, to_user=to_user, to_player=to_player,
                                  body=text, user_ip=request.remote_addr)
                message.save()

                notify_new_message(message)

                return redirect(url_for('messages', username=username))

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
            recipient_filter
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
        ).limit(40)

        # reverse to get newest at the bottom
        messages = list(messages)[::-1]

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

    contacts = get_contact_list(user)

    if not username and not contacts:
        return redirect(url_for('new_message'))

    if username and not messages:
        # show new contact at the top that will be messaged
        contacts.insert(0, {
            'username': username
        })

    template_vars.update({
        'contacts': contacts,
        'messages': messages,
        'username': username,
        'other_user_id': other_user_id
    })

    if not user.email:
        flash(Markup(
            '<a href="%s">Set an email address</a> to receive email notifications for new messages!'
            % url_for('profile_settings')
        ), 'warning')

    return render_template('messages/index.html', **template_vars)


@app.route('/messages/new')
@login_required()
def new_message():
    user = g.user

    contacts = get_contact_list(user)

    template_vars = {
        'new_message': True,
        'contacts': contacts
    }

    return render_template('messages/index.html', **template_vars)


@app.route('/messages/mark_read', methods=['POST'])
@login_required()
def read_message():
    user = g.user
    if not user:
        return jsonify({
            'err': 1,
            'message': 'Must be logged in'
        })

    other_user_id = request.form.get('other_user_id')

    Message.query.filter_by(
        from_user_id=other_user_id,
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


def get_contact_list(user):
    all_messages = Message.query.filter(
        or_(Message.from_user == user, Message.to_user == user)
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
                'user': message.from_user,
                'player': message.from_user.player,
                'username': from_username,
                'last_message_date': message.sent_at,
                'new_message': not message.seen_at
            }

            seen_usernames.add(from_username)
        elif to_username not in seen_usernames and message.to_user != user:
            contact = {
                'user': message.to_user,
                'player': message.to_user.player if message.to_user else message.to_player,
                'username': to_username,
                'last_message_date': message.sent_at,
                'new_message': False
            }

            seen_usernames.add(to_username)

        if contact:
            contacts.append(contact)

    return contacts
