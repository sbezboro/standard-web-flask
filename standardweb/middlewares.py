from flask import request
from flask import request_started
from flask import session

from standardweb import app
from standardweb.models import User

def user_session(sender, **extra):
    if session.get('user_id'):
        print 'lel'
        setattr(request, 'user', User.query.get(session['user_id']))

request_started.connect(user_session, app)
