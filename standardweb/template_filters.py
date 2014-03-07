from jinja2.nodes import Markup

from standardweb import app
from standardweb.lib import helpers as h

from datetime import datetime


def _face_image(username, size):
    cls = 'face-thumb' if size == 16 else 'face-large'
    return '<img src="/face/%(size)d/%(username)s.png" class="%(cls)s" width="%(size)d" height="%(size)d" alt="%(username)s">' \
           % {'size': size, 'cls': cls, 'username': username}


@app.template_filter('face_thumb')
def face_thumb(username):
    return Markup(_face_image(username, 16))


@app.template_filter('face_large')
def face_large(username):
    return Markup(_face_image(username, 64))


@app.template_filter('iso_date')
def iso_date(date):
    #date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
    return h.iso_date(date)
