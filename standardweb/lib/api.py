from standardweb.models import *
from standardweb.lib.constants import *
from standardweb.vendor.minecraft_api import MinecraftJsonApi

import rollbar


apis = {}

def _global_console_command(command):
    for server in Server.query.filter_by(online=True):
        api = get_api(server.address)
        
        api.call('runConsoleCommand', command)


def _api_call(server, type, data=None):
    api = get_api(server.address)

    try:
        if data:
            result = api.call(type, {
                'data': data
            })
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


def get_server_status(server):
    resp = _api_call(server, 'server_status')

    return resp.get('data') if resp else None


def send_player_stats(server, stats):
    _api_call(server, 'player_stats', data=stats)


def send_stats(server, data):
    _api_call(server, 'stats', data=data)


def forum_post(user, forum_name, topic_name, path, is_new_topic=False):
    base_url = url_for('index', _external=True).rstrip('/')
    
    for server in Server.query.filter_by(online=True):
        data = {
            'forum_name': forum_name,
            'topic_name': topic_name,
            'path': '%s%s' % (base_url, path),
            'is_new_topic': is_new_topic
        }

        if user.player:
            data['uuid'] = user.player.uuid
            data['username'] = user.player.username
        else:
            data['username'] = user.username

        _api_call(server, 'forum_post', data=data)


def new_message(to_player, from_user):
    from_username = from_user.get_username()
    from_uuid = from_user.player.uuid if from_user.player else None

    url = url_for('messages', username=from_username, _external=True)

    for server in Server.query.filter_by(online=True):
        data = {
            'from_username': from_username,
            'from_uuid': from_uuid,
            'to_uuid': to_player.uuid,
            'no_user': not to_player.user,
            'url': url
        }

        _api_call(server, 'new_message', data=data)


def set_donator(username):
    _global_console_command('permissions player addgroup %s donator' % username)
