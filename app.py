import logging
import sys

from webassets.script import CommandLineEnvironment
from werkzeug import script

from standardweb import app
from standardweb.assets import env


if __name__ == '__main__':
    if len(sys.argv) == 2:
        if sys.argv[1] == 'shell':
            script.make_shell(lambda: {'app': app}, use_ipython=True)()
        elif sys.argv[1] == 'assets':
            log = logging.getLogger('webassets')
            log.addHandler(logging.StreamHandler())
            log.setLevel(logging.DEBUG)
            cmdenv = CommandLineEnvironment(env, log)
            cmdenv.build()
        else:
            raise Exception('Invalid command')
    else:
        if app.config['DEBUG']:
            from flask_debugtoolbar import DebugToolbarExtension
            DebugToolbarExtension(app)

        app.run(host='0.0.0.0', threaded=True)
