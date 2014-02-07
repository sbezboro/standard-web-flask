from flask import abort
from flask import flash
from flask import redirect
from flask import request
from flask import render_template
from flask import session
from flask import url_for

from standardweb import app
from standardweb.forms import LoginForm
from standardweb.lib import player as libplayer
from standardweb.models import *

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = request.form['username']
        password = request.form['password']
        next = request.form.get('next')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id

            flash('Successfully logged in', 'success')

            return redirect(next or url_for('index'))
        else:
            flash('Invalid username/password combination', 'error')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/player/<username>')
@app.route('/<int:server_id>/player/<username>')
def player(username, server_id=None):
    if not username:
        abort(404)

    if not server_id:
        return redirect(url_for('player', username=username, server_id=2))

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
