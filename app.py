from standardweb import app

if __name__ == '__main__':
    app.config.from_object('settings')
    app.run()