from standardweb.models import *
from standardweb.lib.constants import *
from standardweb.vendor.minecraft_api import MinecraftJsonApi


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
    except Exception as e:
        print e
        return None
    
    if result.get('result') == API_CALL_RESULTS['exception']:
        raise Exception(result.get('message'))
    
    return result


def get_api(host):
    if host not in apis:
        apis[host] = MinecraftJsonApi(host=host,
                                      port=app.config['MC_API_PORT'],
                                      username=app.config['MC_API_USERNAME'],
                                      password=app.config['MC_API_PASSWORD'],
                                      salt=app.config['MC_API_SALT'])
    
    return apis[host]


def get_server_status(server):
    resp = _api_call(server, 'server_status')

    return resp.get('data') if resp else None


def send_player_stats(server, stats):
    _api_call(server, 'player_stats', data=stats)


def send_stats(server, data):
    _api_call(server, 'stats', data=data)


def forum_post(username, forum_name, topic_name, path):
    base_url = url_for('', _external=True)
    
    for server in Server.query.filter_by(online=True):
        data = {
            'username': username,
            'forum_name': forum_name,
            'topic_name': topic_name,
            'path': '%s%s' % (base_url, path)
        }
        _api_call(server, 'forum_post', data=data)


def set_donator(username):
    _global_console_command('permissions player addgroup %s donator' % username)
