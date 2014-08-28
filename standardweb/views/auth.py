from flask import flash
from flask import redirect
from flask import request
from flask import render_template
from flask import session

from standardweb.forms import LoginForm
from standardweb.models import *

from datetime import datetime


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = request.form['username']
        password = request.form['password']
        next_path = request.form.get('next')

        player = Player.query.filter_by(username=username).first()
        if player:
            user = player.user
        else:
            user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session.permanent = True

            if not user.last_login:
                session['first_login'] = True

            user.last_login = datetime.utcnow()
            user.save(commit=True)

            flash('Successfully logged in', 'success')

            return redirect(next_path or url_for('index'))
        else:
            flash('Invalid username/password combination', 'error')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.pop('user_id', None)

    flash('Successfully logged out', 'success')

    return redirect(request.referrer)


@app.route('/signup')
def signup():
    return render_template('signup.html')