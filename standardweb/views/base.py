from datetime import datetime
from datetime import timedelta
import os
from subprocess import call

from flask import abort
from flask import g
from flask import jsonify
from flask import redirect
from flask import request
from flask import render_template
from flask import send_file
from flask import url_for
from PIL import Image
import requests
import rollbar
from sqlalchemy.orm import joinedload
import StringIO

from standardweb import app
from standardweb.lib import leaderboards as libleaderboards
from standardweb.lib import player as libplayer
from standardweb.lib import server as libserver
from standardweb.models import Server, ServerStatus, Player, User
from standardweb.views import redirect_old_url
from standardweb.views.decorators.auth import login_required
from standardweb.views.decorators.cache import last_modified


PROJECT_PATH = os.path.abspath(os.path.dirname(__name__))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/guide')
def guide():
    return render_template('guides/index.html')


@app.route('/guide/groups')
def guide_groups():
    return render_template('guides/groups.html')


@app.route('/search')
def player_search():
    query = request.args.get('q')

    retval = {}

    if query:
        page = request.args.get('p')

        try:
            page = max(int(page), 0) if page else 0
        except:
            page = 0

        page_size = 20

        results = libplayer.filter_players(query, page_size=page_size, page=page)

        retval.update({
            'query': query,
            'results': results,
            'page': page,
            'page_size': page_size
        })

    return render_template('search.html', **retval)


@app.route('/player_list')
def player_list():
    server = Server.query.get(app.config['MAIN_SERVER_ID'])

    stats = libserver.get_player_list_data(server)

    return render_template('includes/playerlist.html', stats=stats)


@app.route('/player_graph')
@app.route('/<int:server_id>/player_graph')
def player_graph(server_id=None):
    server = Server.query.get(server_id or app.config['MAIN_SERVER_ID'])
    if not server:
        abort(404)

    week_index = request.args.get('weekIndex')

    if week_index is None:
        graph_data = libserver.get_player_graph_data(server)
    else:
        first_status = ServerStatus.query.filter_by(server=server).order_by('timestamp').first()

        timestamp = first_status.timestamp + int(week_index) * timedelta(days=7)
        start_date = timestamp
        end_date = timestamp + timedelta(days=7)

        graph_data = libserver.get_player_graph_data(server, start_date=start_date,
                                                     end_date=end_date)

    return jsonify(graph_data)


@app.route('/player/<username>')
@app.route('/<int:server_id>/player/<username>')
def player(username, server_id=None):
    if not username:
        abort(404)

    if not server_id:
        return redirect(url_for('player', username=username,
                                server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)
    if not server:
        abort(404)

    if server.type != 'survival':
        return redirect(url_for('player', username=username,
                                server_id=app.config['MAIN_SERVER_ID']))

    template = 'player.html'
    retval = {
        'server': server,
        'servers': Server.query.filter_by(
            type='survival'
        ).order_by(
            Server.id.desc()
        )
    }

    if len(username) == 32:
        player = Player.query.filter_by(uuid=username).first()
        if player:
            return redirect(url_for('player', username=player.username,
                                    server_id=app.config['MAIN_SERVER_ID']))
    else:
        retval['username'] = username
        player = Player.query.options(
            joinedload(Player.user)
            .joinedload(User.forum_profile)
        ).filter_by(username=username).first()

    if not player:
        # the username doesn't belong to any player seen on any server
        return render_template(template, **retval), 404

    if player.username != username:
        return redirect(url_for('player', username=player.username,
                                server_id=app.config['MAIN_SERVER_ID']))

    # grab all data for this player including the current server data
    data = libplayer.get_data_on_server(player, server)

    # make sure the player has played on at least one survival server
    if not data:
        return render_template(template, **retval), 404

    retval.update({
        'player': player
    })

    retval.update(data)

    return render_template(template, **retval)


@app.route('/ranking')
@app.route('/<int:server_id>/ranking')
def ranking(server_id=None):
    if not server_id:
        return redirect(url_for('ranking', server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)
    if not server:
        abort(404)

    ranking = libserver.get_ranking_data(server)

    retval = {
        'server': server,
        'servers': Server.get_survival_servers(),
        'ranking': ranking
    }

    return render_template('ranking.html', **retval)


@app.route('/leaderboards')
@app.route('/<int:server_id>/leaderboards')
def leaderboards(server_id=None):
    if not server_id:
        return redirect(url_for('leaderboards', server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)

    kill_leaderboards, ore_leaderboards = libleaderboards.get_leaderboard_data(server)

    leaderboard_sections = [{
        'active': True,
        'name': 'Kills',
        'leaderboards': kill_leaderboards
    }, {
        'name': 'Ores',
        'leaderboards': ore_leaderboards
    }]

    retval = {
        'server': server,
        'servers': Server.get_survival_servers(),
        'leaderboard_sections': leaderboard_sections
    }

    return render_template('leaderboards.html', **retval)


def _face_last_modified(username, size=16):
    path = '%s/standardweb/faces/%s/%s.png' % (PROJECT_PATH, size, username)

    try:
        return datetime.utcfromtimestamp(os.path.getmtime(path))
    except:
        return None


@app.route('/face/<username>.png')
@app.route('/face/<int:size>/<username>.png')
@last_modified(_face_last_modified)
def face(username, size=16):
    size = int(size)

    if size not in (16, 64):
        abort(404)

    path = '%s/standardweb/faces/%s/%s.png' % (PROJECT_PATH, size, username)

    url = 'http://skins.minecraft.net/MinecraftSkins/%s.png' % username

    image = None

    try:
        file_date = datetime.utcfromtimestamp(os.path.getmtime(path))
    except Exception:
        file_date = None

    if file_date and datetime.utcnow() - file_date < timedelta(hours=12):
        image = Image.open(path)
    else:
        try:
            resp = requests.get(url, timeout=1)
        except Exception:
            pass
        else:
            if resp.status_code == 200:
                image = libplayer.extract_face(Image.open(StringIO.StringIO(resp.content)), size)
                image.save(path, optimize=True)

                try:
                    call(['optipng', path])
                except OSError:
                    rollbar.report_exc_info(request=request)

    if not image:
        try:
            # try opening existing image if it exists on disk if any of the above fails
            image = Image.open(path)
        except IOError:
            pass

    if not image:
        image = libplayer.extract_face(Image.open(PROJECT_PATH + '/standardweb/static/images/char.png'), size)
        image.save(path)

    tmp = StringIO.StringIO()
    image.save(tmp, 'PNG', optimize=True)
    tmp.seek(0)

    return send_file(tmp, mimetype="image/png")


@app.route('/chat')
@app.route('/<int:server_id>/chat')
def chat(server_id=None):
    if not server_id:
        return redirect(url_for('chat', server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)

    if not server:
        abort(404)

    if not server.online:
        return redirect(url_for('chat', server_id=app.config['MAIN_SERVER_ID']))

    if g.user:
        player = g.user.player
    else:
        player = None

    retval = {
        'server': server,
        'servers': Server.query.all(),
        'player': player
    }

    return render_template('chat.html', **retval)


@app.route('/admin')
@app.route('/<int:server_id>/admin')
@login_required()
def admin(server_id=None):
    if not g.user.admin:
        abort(403)

    if not server_id:
        return redirect(url_for('admin', server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)

    if not server:
        abort(404)

    if not server.online:
        return redirect(url_for('admin', server_id=app.config['MAIN_SERVER_ID']))

    retval = {
        'server': server,
        'servers': Server.query.all()
    }

    return render_template('admin.html', **retval)


@app.errorhandler(403)
def forbidden(e):
    rollbar.report_message('403', request=request)
    return render_template('403.html'), 403


@app.errorhandler(404)
def page_not_found(e):
    rollbar.report_message('404', request=request)
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


redirect_old_url('/faces/<username>.png', 'face', lambda username: {'username': username})
redirect_old_url('/faces/<int:size>/<username>.png', 'face', lambda size, username: {'size': size, 'username': username},
                 append='1')
