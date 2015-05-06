from flask import send_file

from standardweb import app


@app.route('/favicon.ico')
def favicon():
    return send_file('static/favicon.png')


@app.route('/robots.txt')
def robots_txt():
    return send_file('static/robots.txt')


@app.route('/apple-touch-icon.png')
@app.route('/apple-touch-icon-<size>.png')
def apple_touch_icon(size=None):
    return send_file('static/images/logo.png')
