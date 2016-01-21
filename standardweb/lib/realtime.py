from standardweb.tasks.realtime import send_rts_data as send_rts_data_task


def new_message(message):
    payload = {
        'message': message.to_dict()
    }

    send_user_rts_data(message.to_user_id, 'new-message', payload)


def message_read(message):
    payload = {
        'message': message.to_dict()
    }

    send_user_rts_data(message.from_user_id, 'read-message', payload)


def unread_message_count(user):
    payload = {
        'count': user.get_unread_message_count()
    }

    send_user_rts_data(user.id, 'unread-message-count', payload)


def unread_notification_count(user):
    payload = {
        'count': user.get_unread_notification_count()
    }

    send_user_rts_data(user.id, 'unread-notification-count', payload)


def send_user_rts_data(user_id, action, payload):
    send_rts_data(user_id, 'event/user', action, payload)


def send_rts_data(user_id, channel, action, payload):
    send_rts_data_task.apply_async((
        user_id,
        channel,
        action,
        payload
    ))
