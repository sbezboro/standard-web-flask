from standardweb import app

from werkzeug import script

import sys


def make_shell():
    return {
        'app': app
    }

if __name__ == '__main__':
    app.config.from_object('settings')

    if len(sys.argv) == 2 and sys.argv[1] == 'shell':
        script.make_shell(make_shell, use_ipython=True)()
    else:
        if app.config['DEBUG']:
            from flask_debugtoolbar import DebugToolbarExtension
            DebugToolbarExtension(app)

        app.run(threaded=True)