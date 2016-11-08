import rollbar

from standardweb import app
from standardweb.lib.constants import *
from standardweb.models import Server
from standardweb.tasks.server_api import api_forum_post_task
from standardweb.tasks.server_api import api_player_action_task
from standardweb.tasks.server_api import api_new_message_task
from standardweb.vendor.minecraft_api import MinecraftJsonApi


apis = {}


def _global_console_command(command):
    for server in Server.query.filter_by(online=True):
        api = get_api(server.address)

        api.call('runConsoleCommand', command)


def api_call(server, type, data=None):
    api = get_api(server.address)

    try:
        if data:
            result = api.call(type, data)
        else:
            result = api.call(type)
    except Exception:
        rollbar.report_exc_info(
            extra_data={
                'server_id': server.id,
                'type': type,
                'data': data
            }
        )

        return None

    if not result or result.get('result') == API_CALL_RESULTS['exception']:
        extra_data = {
            'server_id': server.id,
            'data': data
        }

        if result:
            extra_data['message'] = result.get('message')
        else:
            extra_data['message'] = 'No result!'

        rollbar.report_message('Exception while calling server API', level='error',
                               extra_data=extra_data)
        return None

    return result


def get_api(host):
    if host not in apis:
        apis[host] = MinecraftJsonApi(
            host=host,
            port=app.config['MC_API_PORT'],
            username=app.config['MC_API_USERNAME'],
            password=app.config['MC_API_PASSWORD'],
            salt=app.config['MC_API_SALT']
        )

    return apis[host]


def get_server_status(server, minimal=False):
    data = {
        'minimal': minimal
    }

    resp = api_call(server, 'server_status', data=data)

    return resp.get('data') if resp else None


def send_player_stats(server, stats):
    api_call(server, 'player_stats', data=stats)


def send_stats(server, data):
    api_call(server, 'stats', data=data)


def ban_player(player, reason, with_ip):
    api_player_action_task.apply_async((
        player.uuid,
        'ban',
        reason,
        None,
        with_ip
    ))


def ban_ip(ip):
    api_player_action_task.apply_async((
        None,
        'ban_ip',
        None,
        ip,
        False
    ))


def forum_post(user, forum_name, topic_name, path, is_new_topic=False):
    api_forum_post_task.apply_async((
        user.get_username(),
        user.player.uuid if user.player else None,
        forum_name,
        topic_name,
        path,
        is_new_topic
    ))


def new_message(to_player, from_user):
    to_user = to_player.user
    if to_user and not _verify_ingame_preference(to_user, 'new_message'):
        return

    api_new_message_task.apply_async((
        to_player.id,
        from_user.id
    ))


def new_notification(player, notification):
    pass


def _verify_ingame_preference(user, type):
    return user.get_notification_preference(type).ingame
