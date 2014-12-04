from flask import abort
from flask import g
from flask import redirect
from flask import request
from flask import render_template
from flask import url_for
from sqlalchemy.orm import joinedload

from standardweb import app
from standardweb.models import Server, Group, Player, PlayerStats


GROUPS_PER_PAGE = 10


@app.route('/groups')
@app.route('/<int:server_id>/groups')
@app.route('/<int:server_id>/groups/<mode>')
def groups(server_id=None, mode=None):
    if not server_id:
        return redirect(url_for('groups', server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)
    if not server:
        abort(404)

    page_size = GROUPS_PER_PAGE

    page = request.args.get('p')

    try:
        page = max(int(page), 1) if page else 1
    except:
        page = 1

    if not mode:
        return redirect(url_for('groups', server_id=server_id, mode='largest'))

    if mode == 'oldest':
        order = Group.established.asc(),
    else:
        order = Group.member_count.desc(), Group.name

    groups = Group.query.options(
        joinedload(Group.members)
    ).filter_by(server=server) \
        .order_by(*order) \
        .limit(page_size) \
        .offset((page - 1) * page_size).all()

    group_count = Group.query.filter_by(server=server).count()

    retval = {
        'server': server,
        'servers': Server.get_survival_servers(),
        'groups': groups,
        'group_count': group_count,
        'page': page,
        'page_size': page_size,
        'mode': mode
    }

    return render_template('groups.html', **retval)


@app.route('/group/<name>')
@app.route('/<int:server_id>/group/<name>')
def group(name, server_id=None):
    if not server_id:
        return redirect(url_for('group', name=name,
                                server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)
    if not server:
        abort(404)

    user = g.user

    group = Group.query.options(
        joinedload(Group.members)
    ).filter_by(server=server, name=name).first()

    if not group:
        return render_template('group.html', name=name), 404

    leader = Player.query.join(PlayerStats)\
        .filter(PlayerStats.server == server, PlayerStats.group == group,
                PlayerStats.is_leader == True).first()

    moderators = Player.query.join(PlayerStats)\
        .filter(PlayerStats.server == server, PlayerStats.group == group,
                PlayerStats.is_moderator == True).all()

    all_members = group.members
    members = filter(lambda x: x != leader and x not in moderators, all_members)

    invites = group.invites

    show_internals = False
    if user:
        show_internals = user.player in all_members or user.admin

    retval = {
        'server': server,
        'group': group,
        'leader': leader,
        'moderators': moderators,
        'members': members,
        'invites': invites,
        'show_internals': show_internals
    }

    return render_template('group.html', **retval)
