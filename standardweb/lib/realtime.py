import pytz

from flask import render_template

from standardweb.tasks import send_rts_data as send_rts_data_task


def new_message(user, message):
    message_row_html = render_template(
        'messages/includes/message_row.html',
        user=user,
        message=message
    )

    payload = {
        'date': message.sent_at.replace(tzinfo=pytz.UTC).isoformat(),
        'message_row_html': message_row_html,
        'from_user_id': message.from_user_id
    }

    send_rts_data(message.to_user_id, 'messages', 'new', payload)


def unread_message_count(user):
    payload = {
        'count': user.get_unread_message_count()
    }

    send_rts_data(user.id, 'messages', 'unread-count', payload)


def send_rts_data(user_id, channel, action, payload):
    send_rts_data_task.apply_async((
        user_id,
        channel,
        action,
        payload
    ))
