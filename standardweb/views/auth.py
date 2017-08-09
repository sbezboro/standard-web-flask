from datetime import datetime, timedelta
import StringIO

from flask import abort, flash, g, redirect, request, render_template, session, url_for, Response
import pyotp
import qrcode
import rollbar
from sqlalchemy import or_

from standardweb import app, stats
from standardweb.forms import LoginForm, VerifyMFAForm, VerifyEmailForm, ForgotPasswordForm, ResetPasswordForm
from standardweb.lib.email import send_reset_password
from standardweb.models import AuditLog, EmailToken, ForumBan, Player, User
from standardweb.views.decorators.auth import login_required
from standardweb.views.decorators.ssl import ssl_required


@app.route('/login', methods=['GET', 'POST'])
@ssl_required()
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = request.form['username']
        password = request.form['password']
        next_path = request.form.get('next')

        username = username.strip()

        player = Player.query.filter_by(username=username).first()
        if player:
            user = player.user
        else:
            # TODO: check renames
            user = User.query.filter(
                or_(User.username == username, User.email == username)
            ).first()

        if user and user.check_password(password):
            if not user.session_key:
                user.generate_session_key(commit=False)

            session['user_session_key'] = user.session_key
            session.permanent = True

            if not user.last_login:
                session['first_login'] = True

            user.last_login = datetime.utcnow()
            user.save(commit=True)

            stats.incr('login.success')

            if user.mfa_login:
                session['mfa_stage'] = 'password-verified'
                return redirect(url_for('verify_mfa', next=next_path))

            flash('Successfully logged in', 'success')

            return redirect(next_path or url_for('index'))
        else:
            flash('Invalid username/password combination', 'error')

            stats.incr('login.invalid')

            AuditLog.create(
                AuditLog.INVALID_LOGIN,
                username=username,
                matched_user_id=user.id if user else None,
                ip=request.remote_addr,
                commit=True
            )

            return render_template('login.html', form=form), 401

    return render_template('login.html', form=form)


@app.route('/verify-mfa', methods=['GET', 'POST'])
def verify_mfa():
    if not session.get('user_session_key'):
        abort(403)

    if session.get('mfa_stage') != 'password-verified':
        abort(403)

    user = User.query.filter_by(
        session_key=session['user_session_key']
    ).first()

    if not user:
        abort(403)

    form = VerifyMFAForm()

    if form.validate_on_submit():
        token = request.form['token']
        next_path = request.form.get('next')

        totp = pyotp.TOTP(user.mfa_secret)

        if totp.verify(token):
            session['mfa_stage'] = 'mfa-verified'
            flash('Successfully logged in', 'success')

            return redirect(next_path or url_for('index'))
        else:
            flash('Invalid code', 'error')

    return render_template('verify_mfa.html', form=form)


@app.route('/mfa-qr-code.png')
@login_required()
def mfa_qr_code():
    user = g.user

    if not user.mfa_secret:
        user.mfa_secret = pyotp.random_base32()
        user.save(commit=True)

    totp = pyotp.TOTP(user.mfa_secret)
    uri = totp.provisioning_uri(user.get_username(), 'Standard Survival')
    image = qrcode.make(uri)

    stream = StringIO.StringIO()
    image.save(stream)
    image = stream.getvalue()

    return Response(image, mimetype='image/png')


@app.route('/logout')
def logout():
    session.pop('user_session_key', None)
    session.pop('mfa_stage', None)

    flash('Successfully logged out', 'success')

    return redirect(url_for('index'))


@app.route('/signup')
def signup():
    return render_template('signup.html')


@app.route('/verify/<token>')
def verify_email(token):
    email_token = EmailToken.query.filter_by(token=token).first()

    result = _check_email_token(email_token, 'verify')
    if result:
        return result

    email_token.date_redeemed = datetime.utcnow()
    email_token.user.email = email_token.email
    email_token.user.save(commit=True)

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
        if g.user.forum_ban:
            session['forum_ban'] = True
            session.permanent = True
        if g.user.player.banned:
            session['player_ban'] = True
            session.permanent = True

        rollbar.report_message(
            'User already logged in when verifying creation email',
            level='warning',
            request=request,
            extra_data={
                'existing_forum_ban': bool(g.user.forum_ban),
                'existing_player_ban': bool(g.user.player.banned)
            }
        )

        session.pop('user_session_key', None)
        g.user = None

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

            if session.get('forum_ban'):
                rollbar.report_message(
                    'Banning user associated with another forum banned user',
                    level='error',
                    request=request
                )
                ban = ForumBan(user_id=user.id)
                ban.save(commit=True)
            if session.get('player_ban'):
                rollbar.report_message(
                    'Banning player associated with another banned player',
                    level='error',
                    request=request
                )
                player.banned = True
                player.save(commit=True)

            session['user_session_key'] = user.session_key
            session['first_login'] = True
            session.permanent = True

            flash('Account created! You are now logged in', 'success')

            stats.incr('account.created')

            rollbar.report_message(
                'Account created',
                level='info',
                request=request,
                extra_data={
                    'user_id': user.id,
                    'player_id': player.id,
                    'username': player.username
                }
            )

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
        rollbar.report_message('User already logged in when resetting password',
                               level='warning', request=request)

        session.pop('user_session_key', None)
        g.user = None

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
            user.generate_session_key(commit=False)
            user.save(commit=True)

            session['user_session_key'] = user.session_key

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
