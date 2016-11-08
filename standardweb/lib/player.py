from datetime import timedelta, datetime

from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func, or_

from standardweb import db
from standardweb.lib import api, cache
from standardweb.lib import helpers as h
from standardweb.models import (
    AuditLog,
    DeathCount,
    KillCount,
    MaterialType,
    OreDiscoveryCount,
    Player,
    PlayerStats,
    Server,
    Title,
    VeteranStatus
)


def extract_face(image, size):
    try:
        pix = image.load()
        for x in xrange(8, 16):
            for y in xrange(8, 16):
                # apply head accessory for non-transparent pixels
                if pix[x + 32, y][3] > 0:
                    pix[x, y] = pix[x + 32, y]
    except:
        pass

    return image.crop((8, 8, 16, 16)).resize((size, size))


def filter_players(query, page_size=None, page=None):
    if page_size is None:
        page_size = 20
    if page is None:
        page = 0

    results = Player.query.filter(
        or_(
            Player.username.ilike('%%%s%%' % query),
            Player.nickname.ilike('%%%s%%' % query)
        )
    ).options(
        joinedload(Player.user)
    ).order_by(
        func.ifnull(Player.nickname, Player.username)
    ).limit(
        page_size
    ).offset(
        page * page_size
    )

    return list(results)


def get_combat_data(player, server):
    pvp_kills = []
    pvp_deaths = []
    other_kills = []
    other_deaths = []

    pvp_kill_count = 0
    pvp_death_count = 0
    other_kill_count = 0
    other_death_count = 0

    deaths = DeathCount.query.filter_by(server=server, victim_id=player.id) \
        .options(joinedload('killer')).options(joinedload('death_type'))

    for death in deaths:
        if death.killer:
            pvp_deaths.append({
                'player': death.killer,
                'count': death.count
            })
            pvp_death_count += death.count
        else:
            other_deaths.append({
                'type': death.death_type.displayname,
                'count': death.count
            })
            other_death_count += death.count

    kills = KillCount.query.filter_by(server=server, killer_id=player.id) \
        .options(joinedload('kill_type'))

    for kill in kills:
        other_kills.append({
            'type': kill.kill_type.displayname,
            'count': kill.count
        })
        other_kill_count += kill.count

    kills = DeathCount.query.filter_by(server=server, killer_id=player.id) \
        .options(joinedload('victim')).options(joinedload('death_type'))

    for kill in kills:
        pvp_kills.append({
            'player': kill.victim,
            'count': kill.count
        })
        pvp_kill_count += kill.count

    pvp_kills = sorted(pvp_kills, key=lambda k: (-k['count'], k['player'].displayname.lower()))
    pvp_deaths = sorted(pvp_deaths, key=lambda k: (-k['count'], k['player'].displayname.lower()))
    other_deaths = sorted(other_deaths, key=lambda k: (-k['count'], k['type']))
    other_kills = sorted(other_kills, key=lambda k: (-k['count'], k['type']))

    return {
        'pvp_kill_count': pvp_kill_count,
        'pvp_death_count': pvp_death_count,
        'pvp_kills': pvp_kills,
        'pvp_deaths': pvp_deaths,
        'other_kill_count': other_kill_count,
        'other_death_count': other_death_count,
        'other_deaths': other_deaths,
        'other_kills': other_kills
    }


@cache.CachedResult('player', time=30)
def get_data_on_server(player, server):
    """
    Returns a dict of all the data for a particular player which
    consists of their global gameplay stats and the stats for the
    given server.
    """
    first_ever_seen = db.session.query(
        func.min(PlayerStats.first_seen)
    ).join(Server).filter(
        PlayerStats.player_id == player.id,
        Server.type == 'survival'
    ).scalar()

    if not first_ever_seen:
        return None

    last_seen = db.session.query(
        func.max(PlayerStats.last_seen)
    ).join(Server).filter(
        PlayerStats.player_id == player.id,
        Server.type == 'survival'
    ).scalar()

    total_time = get_total_player_time(player.id)

    ore_discoveries = OreDiscoveryCount.query.options(
        joinedload(OreDiscoveryCount.material_type)
    ).filter_by(
        player=player,
        server=server
    )

    ore_counts = {type: 0 for type in MaterialType.ORES}

    for ore in ore_discoveries:
        ore_counts[ore.material_type.type] += ore.count

    ore_counts = [(ore.displayname, ore_counts[ore.type]) for ore in MaterialType.get_ores()]

    stats = PlayerStats.query.filter_by(
        server=server,
        player=player
    ).first()

    server_stats = None
    if stats:
        server_stats = {
            'rank': stats.rank,
            'time_spent': h.elapsed_time_string(stats.time_spent),
            'pvp_logs': stats.pvp_logs,
            'group': stats.group,
            'is_leader': stats.is_leader,
            'is_moderator': stats.is_moderator,
            'ore_counts': ore_counts
        }

    online_now = datetime.utcnow() - last_seen < timedelta(minutes=1)

    return {
        'first_ever_seen': first_ever_seen,
        'last_seen': last_seen,
        'online_now': online_now,
        'total_time': h.elapsed_time_string(total_time),
        'combat_stats': get_combat_data(player, server),
        'server_stats': server_stats
    }


@cache.CachedResult('total_player_time', time=300)
def get_total_player_time(player_id):
    return db.session.query(
        func.sum(PlayerStats.time_spent)
    ).join(Server).filter(
        PlayerStats.player_id == player_id,
        Server.type == 'survival'
    ).scalar()


def apply_veteran_titles(player, allow_commit=True):
    update = False
    veteran_statuses = VeteranStatus.query.options(
        joinedload(VeteranStatus.server)
    ).filter_by(player=player)

    for veteran_status in veteran_statuses:
        rank = veteran_status.rank
        server = veteran_status.server

        if rank <= 10:
            veteran_group = 'Top 10 Veteran'
        elif rank <= 40:
            veteran_group = 'Top 40 Veteran'
        else:
            veteran_group = 'Veteran'

        title_name = '%s %s' % (server.abbreviation, veteran_group)
        title = Title.query.filter_by(name=title_name).first()

        if title and title not in player.titles:
            player.titles.append(title)
            update = True

    if update:
        player.save(commit=allow_commit)


def ban_player(player, reason=None, with_ip=False, by_user_id=None, source=None, commit=True, **kwargs):
    reason = reason or 'The Ban Hammer has spoken!'

    api.ban_player(player, reason, with_ip)

    AuditLog.create(
        AuditLog.PLAYER_BAN,
        player_id=player.id,
        username=player.username,
        by_user_id=by_user_id,
        reason=reason,
        source=source,
        commit=False,
        **kwargs
    )

    player.banned = True
    player.save(commit=commit)
