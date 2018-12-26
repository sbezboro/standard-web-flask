from flask_assets import Bundle, Environment
from react.jsx import JSXTransformer
from webassets.filter import Filter, register_filter

from standardweb import app


class React(Filter):
    name = 'react'
    max_debug_level = None

    def output(self, _in, out, **kw):
        content = _in.read()
        transformer = JSXTransformer()
        js = transformer.transform_string(content)
        out.write(js)

register_filter(React)
env = Environment(app)

bundles = {
    'css_all': Bundle(
        Bundle(
            'css/lib/font-awesome.min.css',
            'css/lib/tipsy.css',
            'css/lib/bbcode.css',
        ),
        Bundle(
            'css/local/ansi.less',
            'css/local/base.less',
            'css/local/colors.less',
            'css/local/fonts.less',
            'css/local/layouts.less',
            'css/local/media.less',
            'css/local/mixins.less',
            'css/local/pages/*.less',
            'css/local/style.css',
        ),
        filters='less',
        output='css/gen/all.min.css'
    ),
    'js_lib': Bundle(
        'js/lib/jquery-1.8.3.min.js',
        'js/lib/jquery.flot.min.js',
        'js/lib/jquery.placeholder.min.js',
        'js/lib/jquery.tipsy.min.js',
        'js/lib/jquery.sceditor.min.js',
        'js/lib/jquery.sceditor.bbcode.min.js',
        'js/lib/moment.min.js',
        'js/lib/react-with-addons.min.js',
        'js/lib/socket.io.min.js',
        'js/lib/soundmanager2.min.js',
        'js/lib/ZeroClipboard.min.js',
        filters='uglifyjs',
        output='js/gen/lib.min.js'
    ),
    'js_base': Bundle(
        Bundle(
            'js/local/base.js',
            'js/local/dialog.js',
            'js/local/graph.js',
            'js/local/notifications.js',
            'js/local/realtime.js',
            'js/local/site.js',
        ),
        Bundle(
            'js/local/react/mixins/*.jsx',
            'js/local/react/*.jsx',
            filters='react',
            output='js/gen/react.build.js'  # required for dev
        ),
        filters='uglifyjs',
        output='js/gen/base.min.js'
    ),
    'js_admin': Bundle(
        'js/local/pages/admin.js',
        filters='uglifyjs',
        output='js/gen/admin.min.js'
    ),
    'js_chat': Bundle(
        'js/local/pages/chat.js',
        filters='uglifyjs',
        output='js/gen/chat.min.js'
    ),
    'js_messages': Bundle(
        'js/local/pages/messages.js',
        filters='uglifyjs',
        output='js/gen/messages.min.js'
    )
}

env.register(bundles)
