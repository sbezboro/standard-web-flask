from flask import redirect, url_for

from standardweb import app


def redirect_route(old_rule):
    def decorator(func):
        def redirector(**route_kw):
            return redirect(url_for(func.__name__, **route_kw), 301)

        app.add_url_rule(old_rule, _get_new_url_rule_name(func.__name__), redirector)

        return func

    return decorator


def _get_new_url_rule_name(endpoint):
    val = 1

    while True:
        rule_name = endpoint + '_old_%d' % val

        if not app.view_functions.get(rule_name):
            return rule_name

        val += 1
