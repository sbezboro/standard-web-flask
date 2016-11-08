from flask import abort, g, jsonify, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload

from standardweb import app
from standardweb.lib import helpers as h
from standardweb.lib import player as libplayer
from standardweb.models import IPTracking, Player, Server, User, AuditLog
from standardweb.views.decorators.auth import login_required
from standardweb.views.decorators.redirect import redirect_route


@redirect_route('/forum/user/<username>/')
@app.route('/player/<username>')
@app.route('/<int:server_id>/player/<username>')
def player(username, server_id=None):
    if not username:
        abort(404)

    if not server_id:
        return redirect(url_for('player', username=username,
                                server_id=app.config['MAIN_SERVER_ID']))

    server = Server.query.get(server_id)
    if not server:
        abort(404)

    if server.type != 'survival':
        return redirect(url_for('player', username=username,
                                server_id=app.config['MAIN_SERVER_ID']))

    user = g.user

    template = 'player.html'
    retval = {
        'server': server,
        'servers': Server.query.filter_by(
            type='survival'
        ).order_by(
            Server.id.desc()
        )
    }

    if len(username) in (32, 36):
        player = Player.query.filter_by(uuid=username.replace('-', '')).first()
        if player:
            return redirect(url_for('player', username=player.username,
                                    server_id=server_id))
    else:
        retval['username'] = username
        player = Player.query.options(
            joinedload(Player.user)
            .joinedload(User.forum_profile)
        ).filter_by(username=username).first()

    if not player:
        # the username doesn't belong to any player seen on any server
        return render_template(template, **retval), 404

    if player.username != username:
        return redirect(url_for('player', username=player.username,
                                server_id=app.config['MAIN_SERVER_ID']))

    # grab all data for this player including the current server data
    data = libplayer.get_data_on_server(player, server)

    # make sure the player has played on at least one survival server
    if not data:
        return render_template(template, **retval), 404

    retval.update({
        'player': player
    })

    retval.update(data)

    if user and user.admin_or_moderator:
        ip_tracking_list = IPTracking.query.filter_by(
            player=player
        ).distinct(
            IPTracking.ip
        ).order_by(IPTracking.timestamp.desc()).all()

        ip_addresses = [ip_tracking.ip for ip_tracking in ip_tracking_list]

        same_ip_player_list = Player.query.join(
            IPTracking
        ).filter(
            IPTracking.ip.in_(ip_addresses),
            IPTracking.player != player
        ).distinct(
            IPTracking.player_id
        ).order_by(IPTracking.timestamp.desc()).all()

        retval.update({
            'ip_tracking_list': ip_tracking_list,
            'same_ip_player_list': same_ip_player_list
        })

        if player.banned:
            latest_audit = player.audit_logs.filter(
                AuditLog.player == player,
                AuditLog.type.in_(['player_ban', 'spam_ban', 'spam_shadow_mute_ban'])
            ).order_by(
                AuditLog.timestamp.desc()
            ).first()

            if latest_audit and latest_audit.data:
                retval['ban_time'] = latest_audit.timestamp

                if latest_audit.data.get('reason'):
                    retval['ban_reason'] = latest_audit.data['reason']

                if latest_audit.data.get('by_user_id'):
                    retval['ban_by_user'] = User.query.get(latest_audit.data['by_user_id'])

                if latest_audit.data.get('source'):
                    retval['ban_source'] = latest_audit.data['source']
                elif 'spam' in latest_audit.type:
                    retval['ban_source'] = 'spam'

    return render_template(template, **retval)


@login_required(only_admin=True)
@app.route('/<int:server_id>/player/<uuid>/adjust_time', methods=['POST'])
def adjust_player_time(server_id, uuid):
    server = Server.query.get(server_id)
    if not server:
        abort(404)

    player = Player.query.filter_by(uuid=uuid).first()
    if not player:
        abort(404)

    adjustment = h.to_int(request.form.get('adjustment'))

    if not adjustment:
        abort(400)

    player.adjust_time_spent(server, adjustment, reason='manual', commit=True)

    return jsonify({
        'err': 0
    })


@login_required(only_moderator=True)
@app.route('/player/<uuid>/ban', methods=['POST'])
def ban_player(uuid):
    player = Player.query.filter_by(uuid=uuid).first()
    if not player:
        abort(404)

    reason = request.form.get('reason') or None

    libplayer.ban_player(
        player,
        reason=reason,
        with_ip=True,
        by_user_id=g.user.id,
        source='user_ban_player',
        commit=True
    )

    return jsonify({
        'err': 0
    })
