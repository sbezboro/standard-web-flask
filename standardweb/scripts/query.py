"""
Script that should run every minute. Collects and stores stats from all servers to the db.
"""
from standardweb.models import *
from standardweb.lib import api
from standardweb.lib.constants import *

from datetime import datetime, timedelta

import requests


def _query_server(server, mojang_status):
    server_status = api.get_server_status(server) or {}
    
    player_stats = []
    
    online_player_ids = []
    for player_info in server_status.get('players', []):
        username = player_info['username']
        uuid = player_info['uuid']

        player = Player.query.filter_by(uuid=uuid).first()

        if player:
            if player.username != username:
                player.username = username
                player.save(commit=False)
        else:
            player = Player(username=username, uuid=uuid)
            player.save(commit=False)
        
        online_player_ids.append(player.id)

        last_activity = PlayerActivity.query.filter_by(server=server, player=player)\
            .order_by(PlayerActivity.timestamp.desc()).first()
        
        # if the last activity for this player is an 'exit' activity (or there isn't an activity),
        # create a new 'enter' activity since they just joined this minute
        if not last_activity or last_activity.activity_type == PLAYER_ACTIVITY_TYPES['exit']:
            enter = PlayerActivity(server=server, player=player,
                                   activity_type=PLAYER_ACTIVITY_TYPES['enter'])
            enter.save(commit=False)
        
        # respect nicknames from the main server
        if server.id == app.config['MAIN_SERVER_ID']:
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

        stats = PlayerStats.query.filter_by(server=server, player=player).first()
        if not stats:
            stats = PlayerStats(server=server, player=player)

        stats.last_seen = datetime.utcnow()
        stats.pvp_logs = player_info.get('pvp_logs')
        stats.time_spent = (stats.time_spent or 0) + 1
        stats.save(commit=False)
        
        player_stats.append({
            'username': player.username,
            'uuid': player.uuid,
            'minutes': stats.time_spent,
            'rank': stats.rank
        })
    
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
        'login': mojang_status.login,
        'session': mojang_status.session,
        'account': mojang_status.account,
        'auth': mojang_status.auth
    })


def _get_mojang_status():
    try:
        resp = requests.get('http://status.mojang.com/check')
        result = resp.json()

        website = result[0].get('minecraft.net') == 'green'
        login = result[1].get('login.minecraft.net') == 'green'
        session = result[2].get('session.minecraft.net') == 'green'
        account = result[3].get('account.mojang.com') == 'green'
        auth = result[4].get('auth.mojang.com') == 'green'
        skins = result[5].get('skins.minecraft.net') == 'green'
    except:
        website = False
        login = False
        session = False
        account = False
        auth = False
        skins = False

    mojang_status = MojangStatus(website=website,
                                 login=login,
                                 session=session,
                                 account=account,
                                 auth=auth,
                                 skins=skins)
    mojang_status.save(commit=True)

    return mojang_status


def main():
    app.config.from_object('settings')

    mojang_status = _get_mojang_status()

    for server in Server.query.filter_by(id=5, online=True):
        try:
            _query_server(server, mojang_status)
        except:
            db.session.rollback()
            raise
        else:
            db.session.commit()


if __name__ == '__main__':
    main()
