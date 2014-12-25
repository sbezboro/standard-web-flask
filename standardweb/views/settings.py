import urllib

from flask import abort, flash, g, redirect, render_template, url_for
from markupsafe import Markup

from standardweb import app, db
from standardweb.forms import generate_notification_settings_form, ProfileSettingsForm
from standardweb.lib.email import send_verify_email
from standardweb.lib.notifications import verify_unsubscribe_request
from standardweb.models import EmailToken, User
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

        flash('Notification settings saved!', 'success')

    template_vars = {
        'form': form,
        'preferences': preferences,
        'active_option': 'notifications'
    }

    return render_template('settings/notifications.html', **template_vars)


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
        abort(403)

    email = urllib.unquote(encoded_email)

    user = User.query.filter_by(email=email).first()
    if not user:
        abort(403)

    preference = user.get_notification_preference(type, can_commit=False)
    preference.email = False
    preference.save(commit=True)

    email_preferences_url = url_for('notifications_settings')

    flash(
        Markup('Successfully unsubscribed! Manage more email preferences <a href="%s">here</a>' % email_preferences_url),
        'success'
    )

    return redirect(url_for('index'))
