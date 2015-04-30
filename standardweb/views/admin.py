from flask import abort, redirect, render_template, url_for

from standardweb import app
from standardweb.models import Server
from standardweb.views.decorators.auth import login_required


@app.route('/admin')
@app.route('/<int:server_id>/admin')
@login_required(only_admin=True)
def admin(server_id=None):
    if not server_id:
        return redirect(url_for('admin', server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)

    if not server:
        abort(404)

    if not server.online:
        return redirect(url_for('admin', server_id=app.config['MAIN_SERVER_ID']))

    retval = {
        'server': server,
        'servers': Server.query.all()
    }

    return render_template('admin.html', **retval)
