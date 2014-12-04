import sys

from standardweb import app, db
from standardweb.lib import minecraft_uuid
from standardweb.models import Player


def main():
    app.config.from_object('settings')

    start = 0
    page_size = 10

    if len(sys.argv) == 2:
        start = int(sys.argv[1])

    try:
        while True:
            print start

            players = list(Player.query.order_by('username')
                           .offset(start).limit(page_size))
            if not players:
                break

            usernames = [player.username for player in players]

            profiles = minecraft_uuid.lookup_usernames(usernames)

            uuid_map = {}

            for profile in profiles:
                username = profile['name']
                uuid = profile['id']

                uuid_map[username] = uuid

                print username, uuid

            for player in players:
                player.uuid = uuid_map.get(player.username)
                player.save(commit=False)

            db.session.commit()

            start += page_size
    except:
        db.session.rollback()
        raise
    else:
        db.session.commit()

    print 'Done!'


if __name__ == '__main__':
    main()
