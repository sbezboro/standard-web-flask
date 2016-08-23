from flask import url_for
from sqlalchemy.orm import joinedload

from standardweb import celery
from standardweb.models import Player, PlayerStats, Server, User


@celery.task()
def api_forum_post_task(username, uuid, forum_name, topic_name, path, is_new_topic):
    from standardweb.lib.api import api_call

    base_url = url_for('index', _external=True).rstrip('/')

    for server in Server.query.filter_by(online=True):
        data = {
            'forum_name': forum_name,
            'topic_name': topic_name,
            'path': '%s%s' % (base_url, path),
            'is_new_topic': is_new_topic,
            'username': username
        }

        if uuid:
            data['uuid'] = uuid

        api_call(server, 'forum_post', data=data)


@celery.task()
def api_player_action_task(uuid, action, reason, ip, with_ip):
    from standardweb.lib.api import api_call

    for server in Server.query.filter_by(online=True):
        data = {
            'uuid': uuid,
            'action': action,
            'reason': reason,
            'ip': ip,
            'with_ip': with_ip
        }

        api_call(server, 'player_action', data=data)


@celery.task()
def api_new_message_task(to_player_id, from_user_id):
    from standardweb.lib.api import api_call

    to_player = Player.query.get(to_player_id)
    from_user = User.query.get(from_user_id)

    from_username = from_user.get_username()
    from_uuid = from_user.player.uuid if from_user.player else None

    url = url_for('messages', username=from_username, _external=True)

    player_stats = PlayerStats.query.options(
        joinedload(PlayerStats.server)
    ).filter(
        PlayerStats.player == to_player,
        Server.online == True
    )

    # send the message only if the player is currently on the server
    servers = [player_stat.server for player_stat in player_stats if player_stat.is_online]

    for server in servers:
        data = {
            'from_username': from_username,
            'from_uuid': from_uuid,
            'to_uuid': to_player.uuid,
            'no_user': not to_player.user,
            'url': url
        }

        api_call(server, 'new_message', data=data)