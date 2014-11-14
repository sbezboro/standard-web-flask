from standardweb.lib import api
from standardweb.lib import email


def notify_new_message(message, send_email=True):
    from_user = message.from_user
    user = message.to_user
    player = message.to_player

    if user and send_email:
        # TODO: realtime notification
        email.send_new_message_email(user, message)

    if player:
        api.new_message(player, from_user)
