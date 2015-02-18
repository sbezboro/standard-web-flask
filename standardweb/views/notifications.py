from datetime import datetime
from flask import abort, g, jsonify, redirect, render_template, url_for, request
from sqlalchemy.orm import joinedload

from standardweb import app, db
from standardweb.lib import realtime
from standardweb.models import Notification, User
from standardweb.views.decorators.auth import login_required


@app.route('/notifications')
@login_required()
def notifications():
    user = g.user

    notifications = _get_notifications(user)

    template_vars = {
        'notifications': notifications
    }

    if notifications:
        template_vars['oldest_id'] = notifications[-1].id

    return render_template('notifications/index.html', **template_vars)


@app.route('/notifications/older')
@login_required()
def older_notifications():
    user = g.user

    older_than_id = request.args.get('older_than_id')

    notifications = _get_notifications(user, older_than_id=older_than_id)

    oldest_id = None
    html = ''
    for notification in notifications:
        notification_row_html = render_template(
            'notifications/includes/notification_row.html',
            notification=notification
        )

        html += notification_row_html
        oldest_id = notification.id

    return jsonify({
        'err': 0,
        'html': html,
        'oldest_id': oldest_id
    })


@app.route('/notifications/read/all')
@login_required()
def read_notification_all():
    user = g.user

    Notification.query.filter_by(
        user=user,
        seen_at=None
    ).update({
        'seen_at': datetime.utcnow()
    })

    db.session.commit()

    realtime.unread_notification_count(user)

    return redirect(url_for('notifications'))


@app.route('/notifications/read/<int:notification_id>', methods=['POST'])
@login_required()
def read_notification(notification_id):
    user = g.user

    notification = Notification.query.get(notification_id)
    if not notification:
        abort(404)

    if notification.user != user:
        abort(403)

    notification.seen_at = datetime.utcnow()
    notification.save(commit=True)

    realtime.unread_notification_count(user)

    return jsonify({
        'err': 0
    })


def _get_notifications(user, older_than_id=None):
    notifications = Notification.query.filter(
        Notification.user == user
    ).options(
        joinedload(Notification.user)
        .joinedload(User.player)
    ).order_by(
        Notification.timestamp.desc()
    )

    if older_than_id:
        notifications = notifications.filter(Notification.id < older_than_id)

    return notifications.limit(20).all()
