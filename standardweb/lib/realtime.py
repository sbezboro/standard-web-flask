from standardweb.tasks.realtime import send_rts_data as send_rts_data_task


def new_message(user, message):
    payload = {
        'message': message.to_dict()
    }

    send_rts_data(message.to_user_id, 'messages', 'new', payload)


def unread_message_count(user):
    payload = {
        'count': user.get_unread_message_count()
    }

    send_rts_data(user.id, 'messages', 'unread-count', payload)


def unread_notification_count(user):
    payload = {
        'count': user.get_unread_notification_count()
    }

    send_rts_data(user.id, 'notifications', 'unread-count', payload)


def send_rts_data(user_id, channel, action, payload):
    send_rts_data_task.apply_async((
        user_id,
        channel,
        action,
        payload
    ))
