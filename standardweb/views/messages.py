from flask import abort
from flask import after_this_request
from flask import flash
from flask import g
from flask import render_template
from flask import redirect
from flask import request

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload
from standardweb.forms import MessageForm
from standardweb.lib.notifier import notify_new_message

from standardweb.models import *


MESSAGE_THROTTLE_COUNT = 5
MESSAGE_THROTTLE_PERIOD = 10  # minutes


@app.route('/messages')
@app.route('/messages/<username>', methods=['GET', 'POST'])
def messages(username=None):
    user = g.user

    if not user:
        return redirect(url_for('login', next=request.path))

    messages = []

    form = MessageForm()

    template_vars = {
        'form': form
    }

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

            if len(recent_messages) > MESSAGE_THROTTLE_COUNT:
                flash('Whoa there, you sent too many messages recently! Try sending a bit later.', 'error')
            else:
                message = Message(from_user=user, to_user=to_user, to_player=to_player,
                                  body=text, user_ip=request.remote_addr)
                message.save()

                notify_new_message(message)

                flash('Message sent!', 'success')

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
                    return response

                break

    contacts = get_contact_list(user)

    if username and not messages:
        # show new contact at the top that will be messaged
        contacts.insert(0, {
            'username': username
        })

    template_vars.update({
        'contacts': contacts,
        'messages': messages,
        'username': username
    })

    return render_template('messages/index.html', **template_vars)


@app.route('/messages/new')
def new_message():
    user = g.user

    if not user:
        return redirect(url_for('login', next=request.path))

    contacts = get_contact_list(user)

    template_vars = {
        'new_message': True,
        'contacts': contacts
    }

    return render_template('messages/index.html', **template_vars)


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
