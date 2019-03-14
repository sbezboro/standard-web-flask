from flask import render_template
from sqlalchemy.orm import joinedload

from standardweb import app
from standardweb.models import IPTracking, Player
from standardweb.views.decorators.auth import login_required


@app.route('/ip/<address>')
@login_required(only_admin=True)
def ip_lookup(address):
    ip_tracking_list = IPTracking.query.options(
        joinedload(IPTracking.player)
    ).join(Player).filter(
        IPTracking.ip == address
    ).order_by(
        IPTracking.timestamp.desc()
    )

    retval = {
        'ip_tracking_list': ip_tracking_list,
        'address': address
    }

    return render_template('ip_lookup.html', **retval)
