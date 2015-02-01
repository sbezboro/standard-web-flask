from datetime import datetime
from flask import abort, g, render_template, jsonify
from sqlalchemy.orm import joinedload

from standardweb import app
from standardweb.models import Notification, User
from standardweb.views.decorators.auth import login_required


@app.route('/notifications')
@login_required()
def notifications():
    user = g.user

    notifications = Notification.query.filter(
        Notification.user == user
    ).options(
        joinedload(Notification.user)
        .joinedload(User.player)
    ).order_by(
        Notification.timestamp.desc()
    ).limit(10).all()

    template_vars = {
        'notifications': notifications
    }

    return render_template('notifications/index.html', **template_vars)


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

    return jsonify({
        'err': 0
    })
