from jinja2.nodes import Markup

from standardweb import app
from standardweb.lib import helpers as h


def _face_image(username, size, scaled_size=None):
    scaled_size = scaled_size or size

    cls = 'face-thumb' if size == 16 else 'face-large'
    return '<img src="/face/%(size)d/%(username)s.png" class="%(cls)s" width="%(scaled_size)d" height="%(scaled_size)d" alt="%(username)s">' \
           % {'size': size, 'scaled_size': scaled_size, 'cls': cls, 'username': username}


@app.template_filter('face_thumb')
def face_thumb(username, scaled_size=16):
    return Markup(_face_image(username, 16, scaled_size=scaled_size))


@app.template_filter('face_large')
def face_large(username):
    return Markup(_face_image(username, 64))


@app.template_filter('iso_date')
def iso_date(date):
    return h.iso_date(date)


@app.template_filter('attachment_link')
def attachment_link(attach):
    if attach.content_type in set(['image/png', 'image/gif', 'image/jpeg', 'image/x-png']):
        return Markup('<img src="%s"/>' % attach.url)

    return Markup('%s <a href="%s">%s</a>' % (attach.name, attach.url, attach.name))
