from flask import flash
from flask import g
from flask import redirect
from flask import request
from flask import render_template
from flask import session

from standardweb.forms import LoginForm, VerifyEmailForm, ForgotPasswordForm, ResetPasswordForm
from standardweb.lib.email import send_reset_password
from standardweb.models import *

from datetime import datetime

import rollbar


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


@app.route('/verify/<token>')
def verify_email(token):
    email_token = EmailToken.query.filter_by(token=token).first()

    result = _check_email_token(email_token, 'verify')
    if result:
        return result

    if not g.user:
        flash('You must sign in before verifying an email', 'warning')
        return redirect(url_for('login', next=url_for('verify_email', token=token)))

    if g.user.id != email_token.user_id:
        flash('Link intended for another user', 'warning')
        return redirect(url_for('index'))

    email_token.date_redeemed = datetime.utcnow()

    g.user.email = email_token.email
    g.user.save(commit=True)

    rollbar.report_message('Email verified', level='info', request=request)

    flash('%s verified!' % email_token.email, 'success')

    return redirect(url_for('index'))


@app.route('/create/<token>', methods=['GET', 'POST'])
def create_account(token):
    email_token = EmailToken.query.filter_by(token=token).first()

    result = _check_email_token(email_token, 'creation')
    if result:
        return result

    if g.user:
        session.pop('user_id', None)
        g.user = None

        rollbar.report_message('User already logged in when verifying creation email',
                               level='warning', request=request)

    form = VerifyEmailForm()

    player = Player.query.filter_by(uuid=email_token.uuid).first()
    email = email_token.email

    if form.validate_on_submit():
        password = form.password.data
        confirm_password = form.confirm_password.data

        if password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            email_token.date_redeemed = datetime.utcnow()

            user = User.create(player, password, email)

            session['user_id'] = user.id
            session['first_login'] = True
            session.permanent = True

            flash('Account created! You are now logged in', 'success')

            rollbar.report_message('Account created', level='info', request=request)

            return redirect(url_for('index'))

    return render_template('create_account.html', form=form, player=player,
                           email_token=email_token)


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        email = form.email.data

        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_password(user)

            flash('An email with instructions on resetting your password has been sent!', 'success')

            return redirect(url_for('index'))
        else:
            flash('Email not found', 'error')

    return render_template('forgot_password.html', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email_token = EmailToken.query.filter_by(token=token).first()

    result = _check_email_token(email_token, 'reset_password')
    if result:
        return result

    if g.user:
        session.pop('user_id', None)
        g.user = None

        rollbar.report_message('User already logged in when resetting password',
                               level='warning', request=request)

    form = ResetPasswordForm()

    user = email_token.user

    if form.validate_on_submit():
        password = form.password.data
        confirm_password = form.confirm_password.data

        if password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            email_token.date_redeemed = datetime.utcnow()

            user.set_password(password, commit=False)
            user.last_login = datetime.utcnow()
            user.save(commit=True)

            session['user_id'] = user.id
            session.permanent = True

            flash('Password reset', 'success')

            rollbar.report_message('Password reset', level='info', request=request)

            return redirect(url_for('index'))

    return render_template('reset_password.html', form=form, reset_user=user,
                           email_token=email_token)


def _check_email_token(email_token, type):
    if not email_token:
        flash('Email token not found', 'warning')
        return redirect(url_for('index'))

    if email_token.type != type:
        flash('Invalid email token', 'warning')
        return redirect(url_for('index'))

    if email_token.date_redeemed:
        flash('Link already used', 'warning')
        return redirect(url_for('index'))

    if datetime.utcnow() - email_token.date_created > timedelta(days=2):
        rollbar.report_message('Email token expired', level='warning', request=request)
        flash('This link has expired', 'warning')
        return redirect(url_for('index'))

    return None