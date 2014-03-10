from flask import abort
from flask import flash
from flask import g
from flask import jsonify
from flask import redirect
from flask import request
from flask import render_template
from flask import send_file
from flask import session

from standardweb import app
from standardweb.forms import LoginForm
from standardweb.lib import cache as libcache
from standardweb.lib import leaderboards as libleaderboards
from standardweb.lib import player as libplayer
from standardweb.lib import server as libserver
from standardweb.models import *

from sqlalchemy import or_
from sqlalchemy.sql.expression import func
from sqlalchemy.orm import joinedload

from datetime import datetime
from datetime import timedelta

import StringIO

from PIL import Image

import requests


PROJECT_PATH = os.path.abspath(os.path.dirname(__name__))
TOPICS_PER_PAGE = 40
POSTS_PER_PAGE = 20

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = request.form['username']
        password = request.form['password']
        next_path = request.form.get('next')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session.permanent = True

            flash('Successfully logged in', 'success')

            return redirect(next_path or url_for('index'))
        else:
            flash('Invalid username/password combination', 'error')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/search')
def player_search():
    query = request.args.get('q')
    page = request.args.get('p')

    page = int(page) if page else 0

    page_size = 20

    results = Player.query.filter(or_(Player.username.ilike('%%%s%%' % q),
                                      Player.nickname.ilike('%%%s%%' % q))) \
        .order_by(func.ifnull(Player.nickname, Player.username)) \
        .limit(page_size + 1) \
        .offset(p * page_size)

    results = list(results)

    if len(results) > page_size:
        show_next = True
        results = results[:page_size]
    else:
        show_next = False

    return render_template('search.html', results=results,
                           query=query, page=page,
                           show_next=show_next)


@app.route('/player_list')
def player_list():
    server = Server.query.get(app.config['MAIN_SERVER_ID'])

    stats = libserver.get_player_list_data(server)

    return render_template('includes/playerlist.html', stats=stats)


@app.route('/player_graph')
@app.route('/<int:server_id>/player_graph')
def player_graph(server_id=None):
    server = Server.query.get(server_id or app.config['MAIN_SERVER_ID'])

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

    template = 'player.html'
    retval = {
        'server': server,
        'servers': Server.query.all(),
        'username': username
    }

    player = Player.query.filter_by(username=username).first()
    if not player:
        # the username doesn't belong to any player seen on any server
        return render_template(template, **retval), 404

    # the player has played on at least one server
    retval.update({
        'player': player
    })

    # grab all data for this player on the selected server
    data = libplayer.get_server_data(server, player)

    if not data:
        # the player has not played on the selected server
        retval.update({
            'noindex': True
        })

        return render_template(template, **retval)

    retval.update(data)

    return render_template(template, **retval)


@app.route('/ranking')
@app.route('/<int:server_id>/ranking')
def ranking(server_id=None):
    if not server_id:
        return redirect(url_for('ranking', server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)

    ranking = libserver.get_ranking_data(server)

    retval = {
        'server': server,
        'servers': Server.query.all(),
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
        'servers': Server.query.all(),
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
@libcache.last_modified(_face_last_modified)
def face(username, size=16):
    size = int(size)

    if size != 16 and size != 64:
        abort(404)

    path = '%s/standardweb/faces/%s/%s.png' % (PROJECT_PATH, size, username)

    url = 'http://s3.amazonaws.com/MinecraftSkins/%s.png' % username

    image = None

    try:
        resp = requests.get(url, timeout=1)
    except:
        pass
    else:
        if resp.status_code == 200:
            last_modified = resp.headers['Last-Modified']
            last_modified_date = datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')

            try:
                file_date = datetime.utcfromtimestamp(os.path.getmtime(path))
            except:
                file_date = None

            if not file_date or last_modified_date > file_date \
                or datetime.utcnow() - file_date > timedelta(days=1):
                image = libplayer.extract_face(Image.open(StringIO.StringIO(resp.content)), size)
                image.save(path)
            else:
                image = Image.open(path)

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
    image.save(tmp, 'PNG')
    tmp.seek(0)

    return send_file(tmp, mimetype="image/png")


@app.route('/forums')
def forums():
    categories = ForumCategory.query.options(
        joinedload(ForumCategory.forums)
        .joinedload(Forum.last_post)
        .joinedload(ForumPost.topic)
        .joinedload(ForumTopic.user)
    ).options(
        joinedload(ForumCategory.forums)
        .joinedload(Forum.last_post)
        .joinedload(ForumPost.user)
    ).order_by(ForumCategory.position).all()

    active_forum_ids = set()

    if hasattr(g, 'user'):
        user = g.user
        read_topics = user.posttracking.get_topics()

        if read_topics:
            topics = ForumTopic.query.filter(ForumTopic.id.in_(read_topics.keys()))
            for topic in topics:
                if topic.last_post_id > read_topics.get(topic.id):
                    active_forum_ids.add(topic.forum_id)

    retval = {
        'categories': categories,
        'active_forum_ids': active_forum_ids
    }

    return render_template('forums/index.html', **retval)


@app.route('/forum/<int:forum_id>')
def forum(forum_id):
    forum = Forum.query.get(forum_id)

    if not forum:
        abort(404)

    page_size = TOPICS_PER_PAGE

    page = request.args.get('p')
    page = int(page) if page else 1

    if page < 1 or page > forum.topic_count / page_size + 1:
        return redirect(url_for('forum', forum_id=forum_id))

    topics = ForumTopic.query.options(
        joinedload(ForumTopic.user)
    ).options(
        joinedload(ForumTopic.last_post)
        .joinedload(ForumPost.user)
    ).filter_by(forum_id=forum_id, deleted=False) \
    .order_by(ForumTopic.sticky.desc(), ForumTopic.updated.desc()) \
    .limit(page_size) \
    .offset((page - 1) * page_size)

    topics = list(topics)

    active_topic_ids = set()

    if hasattr(g, 'user'):
        user = g.user
        read_topics = user.posttracking.get_topics()
        last_read = user.posttracking.last_read

        if read_topics:
            for topic in topics:
                if topic.last_post_id > read_topics.get(str(topic.id), 0) \
                        and (not last_read or last_read < topic.updated):
                    active_topic_ids.add(topic.id)

    retval = {
        'forum': forum,
        'topics': topics,
        'active_topic_ids': active_topic_ids,
        'page_size': page_size,
        'page': page
    }

    return render_template('forums/forum.html', **retval)


@app.route('/forums/topic/<int:topic_id>')
def forum_topic(topic_id):
    topic = ForumTopic.query.options(
        joinedload(ForumTopic.forum)
    ).get(topic_id)

    if not topic:
        abort(404)

    page_size = POSTS_PER_PAGE

    page = request.args.get('p')
    page = int(page) if page else 1

    if page < 1 or page > topic.post_count / page_size + 1:
        return redirect(url_for('forum_topic', topic_id=topic_id))

    posts = ForumPost.query.options(
        joinedload(ForumPost.user)
    ).filter_by(topic_id=topic_id) \
    .order_by(ForumPost.created) \
    .limit(page_size) \
    .offset((page - 1) * page_size)

    posts = list(posts)

    if hasattr(g, 'user'):
        topic.update_read(g.user)

    retval = {
        'topic': topic,
        'posts': posts,
        'page_size': page_size,
        'page': page
    }

    return render_template('forums/topic.html', **retval)


@app.route('/forums/post/<int:post_id>')
def forum_post(post_id):
    post = ForumPost.query.get(post_id)

    if not post:
        abort(404)

    topic = post.topic
    if topic.post_count > POSTS_PER_PAGE:
        last_page = int(topic.post_count / POSTS_PER_PAGE) + 1
        return redirect(url_for('forum_topic', topic_id=post.topic_id, p=last_page,_anchor=post.id))

    return redirect(url_for('forum_topic', topic_id=post.topic_id, _anchor=post.id))


@app.route('/chat')
@app.route('/<int:server_id>/chat')
def chat(server_id=None):
    if not server_id:
        return redirect(url_for('chat', server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)

    if g.user:
        player = Player.query.filter_by(username=g.user.username)
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
def admin(server_id=None):
    if not g.user.is_superuser:
        abort(403)

    if not server_id:
        return redirect(url_for('admin', server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)

    retval = {
        'server': server,
        'servers': Server.query.all()
    }

    return render_template('admin.html', **retval)
