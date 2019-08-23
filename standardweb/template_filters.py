import pytz

from jinja2.nodes import Markup

from standardweb import app


def _face_image(uuid, size, scaled_size=None):
    scaled_size = scaled_size or size

    cls = 'face-thumb' if size == 16 else 'face-large'
    return '<img src="/face/%(size)d/%(uuid)s.png" class="%(cls)s" width="%(scaled_size)d" height="%(scaled_size)d">' \
           % {'size': size, 'scaled_size': scaled_size, 'cls': cls, 'uuid': uuid}


@app.template_filter('face_thumb')
def face_thumb(uuid, scaled_size=16):
    return Markup(_face_image(uuid, 16, scaled_size=scaled_size))


@app.template_filter('face_large')
def face_large(uuid):
    return Markup(_face_image(uuid, 64))


@app.template_filter('from_now')
def from_now(date):
    return Markup('<span class="fromnow">%s</span>' % date.replace(tzinfo=pytz.UTC).isoformat())


@app.template_filter('attachment_link')
def attachment_link(attach):
    if attach.content_type in set(['image/png', 'image/gif', 'image/jpeg', 'image/x-png']):
        return Markup('<img src="%s"/>' % attach.url)

    return Markup('%s <a href="%s">%s</a>' % (attach.name, attach.url, attach.name))
