from datetime import datetime, timedelta
import time

import requests
import rollbar
from sqlalchemy import not_
from sqlalchemy.orm import joinedload

from standardweb import app, celery, db
from standardweb import stats as statsd
from standardweb.lib import api, geoip
from standardweb.lib import helpers as h
from standardweb.lib import player as libplayer
from standardweb.lib.constants import *
from standardweb.models import (
    AuditLog, Group, PlayerStats, GroupInvite, Player, PlayerActivity,
    IPTracking, ServerStatus, MojangStatus, Server,
)


def _handle_groups(server, server_groups):
    server_group_uids = [x['uid'] for x in server_groups]

    if not server_group_uids:
        return

    # find all groups that cease to exist on the server, but still exist in db
    deleted_groups = Group.query.filter(
        Group.server == server,
        Group.uid.notin_(server_group_uids)
    )

    deleted_group_ids = [x.id for x in deleted_groups]

    if deleted_group_ids:
        # remove association between players and these about to be deleted groups
        for groupless_player_stat in PlayerStats.query.filter(PlayerStats.group_id.in_(deleted_group_ids)):
            groupless_player_stat.group = None
            groupless_player_stat.is_leader = False
            groupless_player_stat.is_moderator = False
            groupless_player_stat.save(commit=False)

        # remove any pending invites for deleted groups
        for deleted_invite in GroupInvite.query.filter(GroupInvite.group_id.in_(deleted_group_ids)):
            db.session.delete(deleted_invite)

        db.session.flush()

        # delete groups themselves
        for deleted_group in deleted_groups:
            db.session.delete(deleted_group)

        db.session.flush()

    existing_groups = Group.query.filter(
        Group.server == server,
        Group.uid.in_(server_group_uids)
    )

    existing_group_map = {x.uid: x for x in existing_groups}
    group_playerstat_ids = set()

    for group_info in server_groups:
        uid = group_info['uid']
        name = group_info['name']
        established = group_info['established']
        land_count = group_info['land_count']
        land_limit = group_info['land_limit']
        lock_count = group_info['lock_count']
        member_uuids = group_info['member_uuids']
        leader_uuid = group_info['leader_uuid']
        moderator_uuids = group_info['moderator_uuids']
        invites = group_info['invites']

        established = datetime.utcfromtimestamp(established / 1000)
        moderator_uuids = set(moderator_uuids)
        invites = set(invites)

        group = existing_group_map.get(uid)

        if not group:
            group = Group(uid=uid, server=server)

        group.name = name
        group.established = established
        group.land_count = land_count
        group.land_limit = land_limit
        group.member_count = len(member_uuids)
        group.lock_count = lock_count
        group.save(commit=False)

        if member_uuids:
            stats = [p for p in PlayerStats.query.options(
                joinedload(PlayerStats.player)
            ).join(Player).filter(PlayerStats.server == server, Player.uuid.in_(member_uuids))]

            for stat in stats:
                group_playerstat_ids.add(stat.id)

                if stat.player.uuid == leader_uuid:
                    stat.is_leader = True
                    stat.is_moderator = False
                elif stat.player.uuid in moderator_uuids:
                    stat.is_leader = False
                    stat.is_moderator = True
                else:
                    stat.is_leader = False
                    stat.is_moderator = False

                stat.group = group
                stat.save(commit=False)

            if group.id and invites:
                removed_invites = GroupInvite.query.filter(GroupInvite.group_id == group.id,
                                                           not_(GroupInvite.invite.in_(invites)))
                for group_invite in removed_invites:
                    db.session.delete(group_invite)

                existing_invites = GroupInvite.query.filter_by(group=group)
                existing_invites = set([x.invite for x in existing_invites])

                for invite in (invites - existing_invites):
                    group_invite = GroupInvite(group=group, invite=invite)
                    group_invite.save(commit=False)

    groupless_player_stats = PlayerStats.query.filter(
        PlayerStats.server == server,
        PlayerStats.group_id.isnot(None),
        not_(PlayerStats.id.in_(group_playerstat_ids))
    )

    for groupless_player_stat in groupless_player_stats:
        groupless_player_stat.group = None
        groupless_player_stat.is_leader = False
        groupless_player_stat.is_moderator = False
        groupless_player_stat.save(commit=False)

    db.session.commit()


def _query_server(server, mojang_status):
    server_status = api.get_server_status(server) or {}
    
    player_stats = []

    players_to_sync_ban = Player.query.filter(
        Player.uuid.in_(server_status.get('banned_uuids', [])),
        Player.banned == False
    ).all()

    if players_to_sync_ban:
        player_ids_to_sync_ban = [x.id for x in players_to_sync_ban]

        Player.query.filter(
            Player.id.in_(player_ids_to_sync_ban)
        ).update({
            'banned': True,
        }, synchronize_session=False)

        for player in players_to_sync_ban:
            AuditLog.create(
                AuditLog.PLAYER_BAN,
                player_id=player.id,
                username=player.username,
                source='server_sync',
                commit=False
            )

    players = server_status.get('players', [])
    online_player_ids = []
    players_to_nok_ban = []
    for player_info in players:
        username = player_info['username']
        uuid = player_info['uuid']

        player = Player.query.options(
            joinedload(Player.titles)
        ).filter_by(uuid=uuid).first()

        if player:
            if player.username != username:
                h.avoid_duplicate_username(username)

                player.set_username(username)
                player.save(commit=False)
        else:
            h.avoid_duplicate_username(username)

            player = Player(username=username, uuid=uuid)
            player.save(commit=False)

            statsd.incr('player.created')
        
        online_player_ids.append(player.id)

        last_activity = PlayerActivity.query.filter_by(
            server=server, player=player
        ).order_by(
            PlayerActivity.timestamp.desc()
        ).first()
        
        # if the last activity for this player is an 'exit' activity (or there isn't an activity),
        # create a new 'enter' activity since they just joined this minute
        if not last_activity or last_activity.activity_type == PLAYER_ACTIVITY_TYPES['exit']:
            enter = PlayerActivity(server=server, player=player,
                                   activity_type=PLAYER_ACTIVITY_TYPES['enter'])
            enter.save(commit=False)

        if server.id == app.config['MAIN_SERVER_ID']:
            if player.banned:
                player.banned = False
                AuditLog.create(
                    AuditLog.PLAYER_UNBAN,
                    player_id=player.id,
                    username=player.username,
                    source='server_sync',
                    commit=False
                )

            nickname_ansi = player_info.get('nickname_ansi')
            nickname = player_info.get('nickname')

            player.nickname_ansi = nickname_ansi
            player.nickname = nickname
            player.save(commit=False)

        ip = player_info.get('address')
        if ip:
            if not IPTracking.query.filter_by(ip=ip, player=player).first():
                existing_player_ip = IPTracking(ip=ip, player=player)
                existing_player_ip.save(commit=False)

            if geoip.is_nok(ip):
                players_to_nok_ban.append((player, ip))

        stats = PlayerStats.query.filter_by(server=server, player=player).first()
        if not stats:
            stats = PlayerStats(server=server, player=player)

        stats.last_seen = datetime.utcnow()
        stats.pvp_logs = player_info.get('pvp_logs')
        stats.time_spent = (stats.time_spent or 0) + 1
        stats.save(commit=False)

        titles = [{'name': x.name, 'broadcast': x.broadcast} for x in player.titles]

        player_stats.append({
            'username': player.username,
            'uuid': player.uuid,
            'minutes': stats.time_spent,
            'rank': stats.rank,
            'titles': titles
        })

    if len(players) and (float(len(players_to_nok_ban)) / float(len(players))) < 0.5:
        for player, ip in players_to_nok_ban:
            libplayer.ban_player(player, with_ip=True, source='query', ip=ip, commit=False)

    five_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
    result = PlayerStats.query.filter(PlayerStats.server == server,
                                      PlayerStats.last_seen > five_minutes_ago)
    recent_player_ids = [x.player_id for x in result]
    
    # find all players that have recently left and insert an 'exit' activity for them
    # if their last activity was an 'enter'
    for player_id in set(recent_player_ids) - set(online_player_ids):
        latest_activity = PlayerActivity.query.filter_by(server=server, player_id=player_id)\
        .order_by(PlayerActivity.timestamp.desc()).first()
        
        if latest_activity and latest_activity.activity_type == PLAYER_ACTIVITY_TYPES['enter']:
            ex = PlayerActivity(server=server, player_id=player_id,
                                activity_type=PLAYER_ACTIVITY_TYPES['exit'])
            ex.save(commit=False)
    
    player_count = server_status.get('numplayers', 0) or 0
    cpu_load = server_status.get('load', 0) or 0
    tps = server_status.get('tps', 0) or 0
    
    status = ServerStatus(server=server, player_count=player_count, cpu_load=cpu_load, tps=tps)
    status.save(commit=True)

    api.send_stats(server, {
        'player_stats': player_stats,
        'session': mojang_status.session,
        'account': mojang_status.account,
        'auth': mojang_status.auth
    })

    _handle_groups(server, server_status.get('groups', []))


def _get_mojang_status():
    statuses = {}

    try:
        resp = requests.get('http://status.mojang.com/check')
        result = resp.json()

        for status in result:
            for k, v in status.items():
                statuses[k] = v == 'green'
    except:
        pass

    mojang_status = MojangStatus(
        website=statuses.get('minecraft.net', False),
        session=statuses.get('session.minecraft.net', False),
        account=statuses.get('account.mojang.com', False),
        auth=statuses.get('auth.mojang.com', False),
        skins=statuses.get('skins.minecraft.net', False)
    )
    mojang_status.save(commit=True)

    return mojang_status


@celery.task()
def minute_query():
    mojang_status = _get_mojang_status()

    durations = []

    for server in Server.query.filter_by(online=True):
        start = int(round(time.time() * 1000))

        try:
            _query_server(server, mojang_status)
        except:
            db.session.rollback()
            rollbar.report_exc_info(extra_data={'server_id': server.id})
            raise
        else:
            db.session.commit()
            duration = int(round(time.time() * 1000)) - start
            durations.append((server.id, duration))
            print 'Done with server %d in %d milliseconds' % (server.id, duration)

    extra_data = {'server.%d.ms' % server_id: duration for server_id, duration in durations}
    extra_data['session'] = mojang_status.session
    rollbar.report_message('Server queries complete', 'debug',
                           extra_data=extra_data)
