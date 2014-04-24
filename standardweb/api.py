from flask import abort
from flask import g
from flask import jsonify
from flask import request

from functools import wraps

from standardweb.models import *
from standardweb.lib import helpers as h

from sqlalchemy import or_
from sqlalchemy.sql.expression import func


# Base API function decorator that builds a list of view functions for use in urls.py. 
def api_func(function):
    function.csrf_exempt = True
    
    @wraps(function)
    def decorator(*args, **kwargs):
        version = int(kwargs['version'])
        if version < 1 or version > 1:
            abort(404)
        
        del kwargs['version']
        return function(*args, **kwargs)

    name = function.__name__
    app.add_url_rule('/api/v<int:version>/%s' % name, name, decorator)
    
    return decorator


# API function decorator for any api operation exposed to a Minecraft server.
# This access must be authorized by server-id/secret-key pair combination.
def server_api(function):
    @wraps(function)
    def decorator(*args, **kwargs):
        server = None

        if request.headers.get('Authorization'):
            auth = request.headers['Authorization'].split(' ')[1]
            server_id, secret_key = auth.strip().decode('base64').split(':')
        
            #cache_key = 'api-%s-%s' % (server_id, secret_key)
            #server = cache.get(cache_key)
            #if not server:
            server = Server.query.filter_by(id=server_id, secret_key=secret_key).first()
                #cache.set(cache_key, server, 3600)

        if not server:
            abort(403)

        setattr(g, 'server', server)
        
        return function(*args, **kwargs)
    
    return decorator


@api_func
@server_api
def rank_query():
    username = request.args.get('username')
    uuid = request.args.get('uuid')

    if uuid:
        player = Player.query.filter_by(uuid=uuid).first()
    else:
        player = Player.query.filter(or_(Player.username.ilike('%%%s%%' % username),
                                          Player.nickname.ilike('%%%s%%' % username)))\
        .order_by(func.ifnull(Player.nickname, Player.username))\
        .limit(1).first()

    if not player:
        return jsonify({
            'result': 0
        })

    stats = PlayerStats.query.filter_by(server=g.server, player=player).first()
    if not stats:
        return jsonify({
            'result': 0
        })

    time = h.elapsed_time_string(stats.time_spent)

    veteran_status = VeteranStatus.query.filter_by(server_id=1, player=player).first()
    if veteran_status:
        veteran_rank = veteran_status.rank
    else:
        veteran_rank = None

    retval = {
        'result': 1,
        'rank': stats.rank,
        'time': time,
        'minutes': stats.time_spent
    }

    if veteran_rank:
        retval['veteran_rank'] = veteran_rank

    retval['username'] = player.username
    
    return jsonify(retval)


@api_func
def servers(request):
    result = [{
        'id': server.id,
        'address': server.address
    } for server in Server.objects.all()]

    return jsonify(result)

