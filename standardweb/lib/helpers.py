from ansi2html import Ansi2HTMLConverter

import re

_ansi_converter = Ansi2HTMLConverter()
_ansi_pat = re.compile(r'\x1b[^m]*m')
_email_pat = re.compile(r'.+@.+\..+')

def iso_date(date):
    return date.strftime("%Y-%m-%d %H:%M:%SZ")


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


def ansi_to_html(ansi):
    html = _ansi_converter.convert(ansi, full=False)
    count = html.count('<span') - html.count('</span')
    return '<span class="ansi-container">' + html + ('</span>' * count) + '</span>'


def strip_ansi(text):
    return _ansi_pat.sub('', text) if text else None


def is_valid_email(email):
    return _email_pat.match(email)
