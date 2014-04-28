from standardweb import app

from werkzeug import script

import sys


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'shell':
        script.make_shell(lambda: {'app': app}, use_ipython=True)()
    else:
        if app.config['DEBUG']:
            from flask_debugtoolbar import DebugToolbarExtension
            DebugToolbarExtension(app)

        app.run(host='0.0.0.0', threaded=True)