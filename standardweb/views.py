from flask import flash
from flask import redirect
from flask import request
from flask import render_template
from flask import session
from flask import url_for

from standardweb import app
from standardweb.forms import LoginForm
from standardweb.models import User

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
            return redirect(next or url_for('index'))
        else:
            flash('Invalid username/password combination', 'error')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))
