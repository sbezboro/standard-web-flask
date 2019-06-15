from sqlalchemy.orm import joinedload

from standardweb import app
from standardweb.lib import cache
from standardweb.models import KillType, KillCount, MaterialType, OreDiscoveryCount


def _build_kill_leaderboard(server, type):
    kill_type = KillType.query.filter_by(type=type).first()
    kills = KillCount.query.filter_by(server=server, kill_type=kill_type) \
        .options(joinedload('killer')) \
        .order_by(KillCount.count.desc()) \
        .limit(10)
    if kills:
        return sorted([(x.count, x.killer) for x in kills], key=lambda x: (-x[0], x[1].displayname.lower()))[:10]

    return None


def _build_block_discovery_leaderboard(server, type):
    material_type = MaterialType.query.filter_by(type=type).first()
    discoveries = OreDiscoveryCount.query.filter_by(server=server, material_type=material_type) \
        .options(joinedload('player')) \
        .order_by(OreDiscoveryCount.count.desc()) \
        .limit(10)

    if discoveries:
        return sorted([(x.count, x.player) for x in discoveries], key=lambda x: (-x[0], x[1].displayname.lower()))[:10]

    return None


def _get_leaderboard_report(server, type, element, title, section, subtitle):
    func = {
        'kills': _build_kill_leaderboard,
        'ores': _build_block_discovery_leaderboard
    }[type]

    leaderboard_list = func(server, element)

    if leaderboard_list:
        leaderboard_data = {
            'title': title,
            'list': leaderboard_list
        }

        if subtitle:
            leaderboard_data['subtitle'] = subtitle

        section.append(leaderboard_data)


def _get_kill_leaderboards(server, element, title, section, subtitle=None):
    _get_leaderboard_report(server, 'kills', element, title, section, subtitle)


def _get_ore_leaderboards(server, element, title, section, subtitle=None):
    _get_leaderboard_report(server, 'ores', element, title, section, subtitle)


@cache.CachedResult('leaderbaords', time=30)
def get_leaderboard_data(server):
    kill_leaderboards = []
    ore_leaderboards = []

    kill_identifiers = app.config['KILL_LEADERBOARDS']
    material_identifiers = app.config['ORE_LEADERBOARDS']

    kill_types = KillType.query.all()
    kill_type_name_map = {kill_type.type: kill_type.displayname for kill_type in kill_types}

    material_types = MaterialType.query.all()
    meterial_type_name_map = {material_type.type: material_type.displayname for material_type in material_types}

    for identifier in kill_identifiers:
        _get_kill_leaderboards(server, identifier, '%s Kills' % kill_type_name_map[identifier], kill_leaderboards)

    for identifier in material_identifiers:
        _get_ore_leaderboards(server, identifier, '%s Discoveries' % meterial_type_name_map[identifier], ore_leaderboards)

    return kill_leaderboards, ore_leaderboards
