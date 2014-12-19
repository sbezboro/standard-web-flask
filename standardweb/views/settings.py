from flask import flash, g, jsonify, redirect, render_template, url_for

from standardweb import app
from standardweb.forms import ProfileSettingsForm
from standardweb.lib.email import send_verify_email
from standardweb.models import EmailToken
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
        full_name=user.full_name.strip(),
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
