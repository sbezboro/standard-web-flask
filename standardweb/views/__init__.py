from flask import redirect
from flask import request
from flask import url_for

from standardweb import app


def redirect_old_url(old_rule, endpoint, route_kw_func=None, append=None):
    def redirector(**route_kw):
        if route_kw_func:
            return redirect(url_for(endpoint, **route_kw_func(**route_kw)))
        return redirect(url_for(endpoint, **request.args), 301)

    app.add_url_rule(old_rule, endpoint + '_old' + (append if append else ''), redirector)
