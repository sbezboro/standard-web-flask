import re

from ansi2html import Ansi2HTMLConverter

from standardweb import db
from standardweb.lib import minecraft_uuid


_ansi_converter = Ansi2HTMLConverter()
_ansi_pat = re.compile(r'\x1b[^m]*m')
_email_pat = re.compile(r'.+@.+\..+')


def elapsed_time_string(total_minutes):
    hours = int(total_minutes / 60)

    if not hours:
        return '%d %s' % (total_minutes, 'minute' if total_minutes == 1 else 'minutes')

    minutes = total_minutes % (hours * 60)

    return '%d %s %d %s' % (hours, 'hour' if hours == 1 else 'hours',
                            minutes, 'minute' if minutes == 1 else 'minutes')


def safe_str_cmp(a, b):
    if len(a) != len(b):
        return False
    rv = 0
    for x, y in zip(a, b):
        rv |= ord(x) ^ ord(y)
    return rv == 0


# temporary workaround
# maps section sign codes to real ansi codes, as paperspigot doesn't seem to include jansi in the runtime
_ansi_mc_map = {
    u"\xa70": u"\x1B[0;30;22m", # Black 0
    u"\xa71": u"\x1B[0;34;22m", # Dark Blue 1
    u"\xa72": u"\x1B[0;32;22m", # Dark Green 2
    u"\xa73": u"\x1B[0;36;22m", # Dark Aqua 3
    u"\xa74": u"\x1B[0;31;22m", # Dark Red 4
    u"\xa75": u"\x1B[0;35;22m", # Dark Purple 5
    u"\xa76": u"\x1B[0;33;22m", # Gold 6
    u"\xa77": u"\x1B[0;37;22m", # Gray 7
    u"\xa78": u"\x1B[0;30;1m",  # Dark Gray 8
    u"\xa79": u"\x1B[0;34;1m",  # Blue 9
    u"\xa7a": u"\x1B[0;32;1m",  # Green a
    u"\xa7b": u"\x1B[0;36;1m",  # Aqua b
    u"\xa7c": u"\x1B[0;31;1m",  # Red c
    u"\xa7d": u"\x1B[0;35;1m",  # Light Purple d
    u"\xa7e": u"\x1B[0;33;1m",  # Yellow e
    u"\xa7f": u"\x1B[0;37;1m",  # White f
    u"\xa7k": u"\x1B[5m",       # Obfuscated k
    u"\xa7l": u"\x1B[21m",      # Bold l
    u"\xa7m": u"\x1B[9m",       # Strikethrough m
    u"\xa7n": u"\x1B[4m",       # Underline n
    u"\xa7o": u"\x1B[3m",       # Italic o
    u"\xa7r": u"\x1B[39;0m",    # Reset r
}

_ansi_mc_map_regexp = {}
for code in _ansi_mc_map:
    _ansi_mc_map_regexp[code] = re.compile(re.escape(code), re.IGNORECASE)


def ansi_to_html(ansi):
    for code in _ansi_mc_map:
        ansi = _ansi_mc_map_regexp[code].sub(_ansi_mc_map[code], ansi)
    html = _ansi_converter.convert(ansi, full=False)
    count = html.count('<span') - html.count('</span')
    return '<span class="ansi-container">' + html + ('</span>' * count) + '</span>'


def strip_ansi(text):
    return _ansi_pat.sub('', text) if text else None


def is_valid_email(email):
    return _email_pat.match(email)


def to_int(value):
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def avoid_duplicate_username(username, allow_flush=True):
    """catch case if player on the server has renamed to an existing username in the db,
    look up existing player's current username since it must be different now
    """
    from standardweb.models import Player
    existing_username_player = Player.query.filter_by(username=username).first()
    if existing_username_player:
        new_username = minecraft_uuid.lookup_latest_username_by_uuid(existing_username_player.uuid)
        existing_username_player.set_username(new_username)
        existing_username_player.save(commit=False)

        if allow_flush:
            db.session.flush()
