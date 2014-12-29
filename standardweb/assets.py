from flask.ext.assets import Bundle, Environment

from standardweb import app


env = Environment(app)

js = Bundle(
    Bundle(
        'js/thirdparty/jquery-1.8.3.min.js',
        'js/thirdparty/jquery.flot.min.js',
        'js/thirdparty/jquery.placeholder.min.js',
        'js/thirdparty/jquery.tipsy.min.js',
        'js/thirdparty/jquery.sceditor.min.js',
        'js/thirdparty/jquery.sceditor.bbcode.min.js',
        'js/thirdparty/moment.min.js',
        'js/thirdparty/socket.io.min.js',
        'js/thirdparty/soundmanager2.min.js',
        'js/thirdparty/ZeroClipboard.min.js'
    ),
    Bundle(
        'js/local/base.js',
        'js/local/chat.js',
        'js/local/console.js',
        'js/local/graph.js',
        'js/local/messages.js',
        'js/local/realtime.js',
        'js/local/site.js'
    ),
    filters='uglifyjs',
    output='js/gen/all.min.js'
)

css = Bundle(
    Bundle(
        'css/thirdparty/font-awesome.min.css',
        'css/thirdparty/tipsy.css',
        'css/thirdparty/bbcode.css',
    ),
    Bundle(
        'css/local/base.less',
        'css/local/colors.less',
        'css/local/layouts.less',
        'css/local/media.less',
        'css/local/mixins.less',
        'css/local/pages/index.less',
        'css/local/style.css',
    ),
    filters='less',
    output='css/gen/all.min.css'
)

env.register('js_all', js)
env.register('css_all', css)
