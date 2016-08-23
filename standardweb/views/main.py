from datetime import datetime
from datetime import timedelta
import os
import subprocess

from flask import abort, flash, g, jsonify, redirect, request, render_template, send_file, url_for
from PIL import Image
import requests
import rollbar
import StringIO

from standardweb import app
from standardweb.lib import api
from standardweb.lib import leaderboards as libleaderboards
from standardweb.lib import player as libplayer
from standardweb.lib import server as libserver
from standardweb.models import Server, ServerStatus, MojangStatus
from standardweb.views.decorators.cache import last_modified
from standardweb.views.decorators.redirect import redirect_route


PROJECT_PATH = os.path.abspath(os.path.dirname(__name__))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/help')
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


@redirect_route('/faces/<username>.png')
@redirect_route('/faces/<int:size>/<username>.png')
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
                    subprocess.Popen(['optipng', path], stderr=subprocess.PIPE)
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

    if player and player.banned:
        api.ban_player(player)

    status = MojangStatus.query.order_by(MojangStatus.timestamp.desc()).limit(1).first()
    if status and not status.session:
        flash(
            'Minecraft session servers are down, you may not be able to join the server!',
            category='warning'
        )

    return render_template('chat.html', **retval)


@app.errorhandler(403)
def forbidden(e):
    rollbar.report_message('Forbidden', request=request)
    return render_template('403.html'), 403


@app.errorhandler(404)
def page_not_found(e):
    rollbar.report_message('404', request=request)
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500
