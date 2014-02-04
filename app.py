from standardweb import app

if __name__ == '__main__':
    app.config.from_object('settings')

    if app.config['DEBUG']:
        from flask_debugtoolbar import DebugToolbarExtension
        DebugToolbarExtension(app)

    app.run()