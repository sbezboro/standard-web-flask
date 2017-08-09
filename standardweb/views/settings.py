import urllib

from flask import abort, flash, g, redirect, render_template, request, url_for, session
from markupsafe import Markup
import pyotp
import rollbar

from standardweb import app, db
from standardweb.forms import (
    generate_notification_settings_form,
    AddMFAForm,
    ProfileSettingsForm,
    ChangePasswordForm,
    RemoveMFAForm
)
from standardweb.lib.email import send_verify_email
from standardweb.lib.notifications import verify_unsubscribe_request
from standardweb.models import EmailToken, User, AuditLog
from standardweb.views.decorators.auth import login_required


def _get_unverified_email(user):
    unverified_email_token = EmailToken.query.filter_by(
        user=user,
        type='verify',
        date_redeemed=None
    ).order_by(
        EmailToken.date_created.desc()
    ).first()

    if unverified_email_token:
        return unverified_email_token.email

    return None


@app.route('/settings')
def settings():
    return redirect(url_for('profile_settings'))


@app.route('/settings/profile', methods=['GET', 'POST'])
@login_required()
def profile_settings():
    user = g.user

    form = ProfileSettingsForm(
        full_name=(user.full_name or '').strip(),
        email=user.email
    )

    if form.validate_on_submit():
        full_name = form.full_name.data
        email = form.email.data

        user.full_name = full_name

        if email != user.email:
            send_verify_email(email, user)

            flash('Verification email sent to %s' % email, 'success')
        else:
            flash('Profile saved!', 'success')

        user.save()

    unverified_email = _get_unverified_email(user)

    template_vars = {
        'form': form,
        'unverified_email': unverified_email,
        'player': user.player,
        'active_option': 'profile'
    }

    return render_template('settings/profile.html', **template_vars)


@app.route('/settings/notifications', methods=['GET', 'POST'])
@login_required()
def notifications_settings():
    user = g.user

    preferences = user.get_notification_preferences()

    form = generate_notification_settings_form(preferences)

    if form.validate_on_submit():
        for preference in preferences:
            preference.email = getattr(form, '%s_email' % preference.name).data
            preference.ingame = getattr(form, '%s_ingame' % preference.name).data

            preference.save(commit=False)

        db.session.commit()

        AuditLog.create('notification_settings_saved', user_id=user.id, data={
            x.name: {
                'email': x.email,
                'ingame': x.ingame
            } for x in preferences
        }, commit=True)

        flash('Notification settings saved!', 'success')

    grouped_preferences = {}
    for preference in preferences:
        definition = preference.definition
        grouped_preferences.setdefault(definition.setting_category, []).append(preference)

    template_vars = {
        'form': form,
        'grouped_preferences': grouped_preferences,
        'active_option': 'notifications'
    }

    return render_template('settings/notifications.html', **template_vars)


@app.route('/settings/change_password', methods=['GET', 'POST'])
@login_required()
def change_password_settings():
    user = g.user

    form = ChangePasswordForm()

    if form.validate_on_submit():
        current_password = form.current_password.data
        new_password = form.new_password.data
        confirm_new_password = form.confirm_new_password.data

        if not user.check_password(current_password):
            form.current_password.errors = ['Incorrect']
        elif new_password != confirm_new_password:
            form.new_password.errors = ['Passwords do not match']
            form.confirm_new_password.errors = ['Passwords do not match']
        else:
            user.set_password(new_password, commit=False)
            user.generate_session_key(commit=False)

            session['user_session_key'] = user.session_key

            user.save(commit=True)

            flash('Password changed', 'success')

    template_vars = {
        'form': form,
        'active_option': 'change_password'
    }

    return render_template('settings/change_password.html', **template_vars)


@app.route('/settings/profile/resend_verification_email')
@login_required()
def resend_verification_email():
    user = g.user

    unverified_email = _get_unverified_email(user)

    if unverified_email:
        send_verify_email(unverified_email, user)

        flash('Verification email sent to %s' % unverified_email, 'success')
    else:
        flash('No unverified email', 'warning')

    return redirect(url_for('profile_settings'))


@app.route('/unsubscribe/<encoded_email>/<type>/<signature>')
def unsubscribe(encoded_email, type, signature):
    if not verify_unsubscribe_request(encoded_email, type, signature):
        rollbar.report_message('Unsubscribe signature failure', level='error', extra_data={
            'current_user_id': g.user.id if g.user else None,
            'path': request.path,
        })

        abort(403)

    email = urllib.unquote(encoded_email)

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Invalid link', 'error')
        return redirect(url_for('index'))

    if g.user and g.user != user:
        rollbar.report_message('Unsubscribing email of a different user', level='warning', extra_data={
            'current_user_id': g.user.id,
            'current_user_email': g.user.email,
            'target_user_id': user.id,
            'target_user_email': email
        })

    AuditLog.create('unsubscribe', user_id=g.user.id if g.user else user.id, data={
        'email': email,
        'type': type
    }, commit=False)

    preference = user.get_notification_preference(type, can_commit=False)
    preference.email = False
    preference.save(commit=True)

    email_preferences_url = url_for('notifications_settings')

    flash(
        Markup('Successfully unsubscribed! Manage more email preferences <a href="%s">here</a>.' % email_preferences_url),
        'success'
    )

    return redirect(url_for('index'))


@app.route('/settings/mfa', methods=['GET', 'POST'])
@login_required()
def mfa_settings():
    user = g.user

    if user.mfa_login:
        form = RemoveMFAForm()

        if form.validate_on_submit():
            session['mfa_stage'] = None
            user.mfa_login = False
            user.save(commit=True)

            flash('Disabled two-factor authentication', 'success')

            return redirect(url_for('mfa_settings'))
    else:
        form = AddMFAForm()

        if form.validate_on_submit():
            token = request.form['token']
            totp = pyotp.TOTP(user.mfa_secret)

            if totp.verify(token):
                session['mfa_stage'] = 'mfa-verified'
                user.mfa_login = True
                user.save(commit=True)

                flash('Successfully enabled two-factor authentication', 'success')

                return redirect(url_for('mfa_settings'))
            else:
                form.token.errors = ['Invalid code']

    template_vars = {
        'form': form,
        'active_option': 'mfa'
    }

    return render_template('settings/mfa.html', **template_vars)
