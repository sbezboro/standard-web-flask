import logging

from fabric.api import abort, run, local, cd, env, roles, execute, prefix
import requests
from webassets.script import CommandLineEnvironment
from werkzeug import script

from standardweb import app
from standardweb.assets import env as assets_env


CODE_DIR = '/home/deploy/standard-web-flask'
ENV_DIR = '/home/deploy/standard-web-flask/env'
WEB_SERVICE = 'standard-web-flask'
TASK_SERVICE = 'standard-web-celery'
SCHEDULE_SERVICE = 'standard-web-celery-beat'

env.user = 'deploy'
env.roledefs = {
    'web': ['107.191.37.51'],
    'graphite': ['107.191.37.51']
}


def deploy():
    execute(_update_and_restart_services)
    _rollbar_record_deploy()
    execute(_graphite_record_deploy)


def serve():
    from flask_debugtoolbar import DebugToolbarExtension
    DebugToolbarExtension(app)

    app.run(host='0.0.0.0', threaded=True)


def shell():
    script.make_shell(lambda: {'app': app}, use_ipython=True)()


def build_assets():
    log = logging.getLogger('webassets')
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.DEBUG)

    cmdenv = CommandLineEnvironment(assets_env, log)
    cmdenv.build()


@roles('web')
def _update_and_restart_services():
    with cd(CODE_DIR):
        with prefix('source %s/bin/activate' % ENV_DIR):
            run("git pull")

            result = run("npm install --quiet")
            if result.failed:
                abort('Could not install required node modules. Aborting.')

            result = run("pip install -r requirements.txt --quiet")
            if result.failed:
                abort('Could not install required packages. Aborting.')

            run('fab build_assets')

            run('supervisorctl restart %s' % WEB_SERVICE)
            run('supervisorctl restart %s' % TASK_SERVICE)
            run('supervisorctl restart %s' % SCHEDULE_SERVICE)


def _rollbar_record_deploy():
    access_token = app.config['ROLLBAR_ACCESS_TOKEN']
    environment = 'production'

    username = local('whoami', capture=True)
    revision = local('git log -n 1 --pretty=format:"%H"', capture=True)

    resp = requests.post('https://api.rollbar.com/api/1/deploy/', {
        'access_token': access_token,
        'environment': environment,
        'local_username': username,
        'rollbar_username': username,
        'revision': revision
    }, timeout=3)

    if resp.status_code == 200:
        print "Deploy recorded successfully."
    else:
        print "Error recording deploy:", resp.text


@roles('graphite')
def _graphite_record_deploy():
    run('echo "events.deploy 1 `date +%%s`" | nc %s %s' % (
        app.config['GRAPHITE_HOST'], app.config['GRAPHITE_PORT']
    ))
