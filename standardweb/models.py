from flask import json
from flask import url_for

from standardweb import app
from standardweb import db
from standardweb.lib import helpers as h

from pbkdf2 import pbkdf2_bin

from sqlalchemy.exc import IntegrityError

from datetime import datetime, timedelta

import binascii
import hashlib
import os
import re


def _get_or_create(cls, **kwargs):
    query = cls.query.filter_by(**kwargs)

    instance = query.first()

    if instance:
        return instance, False
    else:
        db.session.begin(nested=True)
        try:
            instance = cls(**kwargs)

            db.session.add(instance)
            db.session.commit()

            return instance, True
        except IntegrityError:
            db.session.rollback()
            instance = query.one()

            return instance, False


class Base(object):
    def save(self, commit=True):
        db.session.add(self)

        if commit:
            db.session.commit()

    @classmethod
    def factory(cls, **kwargs):
        instance, created = _get_or_create(cls, **kwargs)

        return instance


class User(db.Model, Base):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    uuid = db.Column(db.String(32))
    email = db.Column(db.String(75))
    password = db.Column(db.String(128))
    admin = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)

    player = db.relationship('Player', backref=db.backref('user', uselist=False))

    @classmethod
    def create(cls, player, plaintext_password, commit=True):
        user = cls(player=player, uuid=player.uuid)
        user.set_password(plaintext_password)

        user.save(commit=False)

        forum_profile = ForumProfile(user=user)
        forum_profile.save(commit=commit)

        return user

    def check_password(self, plaintext_password):
        algorithm, iterations, salt, hash_val = self.password.split('$', 3)
        expected = User._make_password(plaintext_password, salt=salt, iterations=int(iterations))

        return h.safe_str_cmp(self.password, expected)

    def set_password(self, plaintext_password, commit=True):
        password = User._make_password(plaintext_password)
        self.password = password
        self.save(commit=commit)

    @staticmethod
    def _make_password(password, salt=None, iterations=None):
        if not salt:
            salt = binascii.b2a_hex(os.urandom(15))

        if not iterations:
            iterations = 10000

        hash_val = pbkdf2_bin(bytes(password), bytes(salt), iterations, keylen=32, hashfunc=hashlib.sha256)
        hash_val = hash_val.encode('base64').strip()
        return '%s$%s$%s$%s' % ('pbkdf2_sha256', iterations, salt, hash_val)


class Player(db.Model, Base):
    __tablename__ = 'player'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(32))
    username = db.Column(db.String(30))
    nickname = db.Column(db.String(30))
    nickname_ansi = db.Column(db.String(256))

    def __str__(self):
        return self.displayname

    @property
    def nickname_html(self):
        return h.ansi_to_html(self.nickname_ansi) if self.nickname_ansi else None

    @property
    def displayname(self):
        return self.nickname or self.username

    @property
    def displayname_html(self):
        return self.nickname_html if self.nickname else self.username


class PlayerStats(db.Model, Base):
    __tablename__ = 'playerstats'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    time_spent = db.Column(db.Integer, default=0)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    banned = db.Column(db.Boolean, default=False)
    pvp_logs = db.Column(db.Integer, default=0)

    server = db.relationship('Server')
    player = db.relationship('Player')

    @property
    def is_online(self):
        return datetime.utcnow() - self.last_seen < timedelta(minutes=1)

    @property
    def rank(self):
        return PlayerStats.query.filter(PlayerStats.server_id == self.server_id,
                                        PlayerStats.time_spent > self.time_spent,
                                        PlayerStats.player_id != self.player_id).count() + 1

class Server(db.Model, Base):
    __tablename__ = 'server'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30))
    address = db.Column(db.String(50))
    online = db.Column(db.Boolean())
    secret_key = db.Column(db.String(10))


class ServerStatus(db.Model, Base):
    __tablename__ = 'serverstatus'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    player_count = db.Column(db.Integer, default=0)
    cpu_load = db.Column(db.Float, default=0)
    tps = db.Column(db.Float, default=0)

    server = db.relationship('Server')


class MojangStatus(db.Model, Base):
    __tablename__ = 'mojangstatus'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    website = db.Column(db.Boolean)
    login = db.Column(db.Boolean)
    session = db.Column(db.Boolean)
    account = db.Column(db.Boolean)
    auth = db.Column(db.Boolean)
    skins = db.Column(db.Boolean)


class DeathType(db.Model, Base):
    __tablename__ = 'deathtype'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100))
    displayname = db.Column(db.String(100))


class KillType(db.Model, Base):
    __tablename__ = 'killtype'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100))
    displayname = db.Column(db.String(100))


class DeathEvent(db.Model, Base):
    __tablename__ = 'deathevent'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    death_type_id = db.Column(db.Integer, db.ForeignKey('deathtype.id'))
    victim_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    killer_id = db.Column(db.Integer, db.ForeignKey('player.id'))

    server = db.relationship('Server')
    death_type = db.relationship('DeathType')
    killer = db.relationship('Player', foreign_keys='DeathEvent.killer_id')
    victim = db.relationship('Player', foreign_keys='DeathEvent.victim_id')


class KillEvent(db.Model, Base):
    __tablename__ = 'killevent'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    kill_type_id = db.Column(db.Integer, db.ForeignKey('killtype.id'))
    killer_id = db.Column(db.Integer, db.ForeignKey('player.id'))

    server = db.relationship('Server')
    kill_type = db.relationship('KillType')
    killer = db.relationship('Player')


class DeathCount(db.Model, Base):
    __tablename__ = 'deathcount'

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    death_type_id = db.Column(db.Integer, db.ForeignKey('deathtype.id'))
    victim_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    killer_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    count = db.Column(db.Integer, default=0)

    server = db.relationship('Server')
    death_type = db.relationship('DeathType')
    killer = db.relationship('Player', foreign_keys='DeathCount.killer_id')
    victim = db.relationship('Player', foreign_keys='DeathCount.victim_id')

    @classmethod
    def increment(cls, server, death_type, victim, killer, commit=True):
        death_count = cls.factory(server=server,
                                  death_type=death_type,
                                  victim=victim,
                                  killer=killer)
        death_count.count = (death_count.count or 0) + 1
        death_count.save(commit=commit)


class KillCount(db.Model, Base):
    __tablename__ = 'killcount'

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    kill_type_id = db.Column(db.Integer, db.ForeignKey('killtype.id'))
    killer_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    count = db.Column(db.Integer, default=0)

    server = db.relationship('Server')
    kill_type = db.relationship('KillType')
    killer = db.relationship('Player')

    @classmethod
    def increment(cls, server, kill_type, killer, commit=True):
        kill_count = cls.factory(server=server,
                                 kill_type=kill_type,
                                 killer=killer)
        kill_count.count = (kill_count.count or 0) + 1
        kill_count.save(commit=commit)


class MaterialType(db.Model, Base):
    __tablename__ = 'materialtype'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(32), unique=True)
    displayname = db.Column(db.String(64))


class OreDiscoveryEvent(db.Model, Base):
    __tablename__ = 'orediscoveryevent'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    material_type_id = db.Column(db.Integer, db.ForeignKey('materialtype.id'))
    x = db.Column(db.Integer)
    y = db.Column(db.Integer)
    z = db.Column(db.Integer)

    server = db.relationship('Server')
    player = db.relationship('Player')
    material_type = db.relationship('MaterialType')


class OreDiscoveryCount(db.Model, Base):
    __tablename__ = 'orediscoverycount'

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    material_type_id = db.Column(db.Integer, db.ForeignKey('materialtype.id'))
    count = db.Column(db.Integer, default=0)

    server = db.relationship('Server')
    player = db.relationship('Player')
    material_type = db.relationship('MaterialType')

    @classmethod
    def increment(cls, server, material_type, player, commit=True):
        ore_count = cls.factory(server=server,
                                material_type=material_type,
                                player=player)
        ore_count.count = (ore_count.count or 0) + 1
        ore_count.save(commit=commit)


class IPTracking(db.Model, Base):
    __tablename__ = 'iptracking'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip = db.Column(db.String(15))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    player = db.relationship('Player')
    user = db.relationship('User')


class PlayerActivity(db.Model, Base):
    __tablename__ = 'playeractivity'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    activity_type = db.Column(db.Integer)

    server = db.relationship('Server')
    player = db.relationship('Player')


player_title = db.Table('player_title',
    db.Column('player_id', db.Integer, db.ForeignKey('player.id')),
    db.Column('title_id', db.Integer, db.ForeignKey('title.id')))


class Title(db.Model, Base):
    __tablename__ = 'title'

    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    name = db.Column(db.String(20))
    displayname = db.Column(db.String(40))

    players = db.relationship('Player', secondary=player_title,
                              backref=db.backref('titles'))


class VeteranStatus(db.Model, Base):
    __tablename__ = 'veteranstatus'

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    rank = db.Column(db.Integer)

    player = db.relationship('Player')


class ForumProfile(db.Model, Base):
    __tablename__ = 'forum_profile'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_count = db.Column(db.Integer, default=0)
    signature = db.Column(db.Text())
    signature_html = db.Column(db.Text())

    user = db.relationship('User', backref=db.backref('forum_profile', uselist=False))


class ForumCategory(db.Model, Base):
    __tablename__ = 'forum_category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    position = db.Column(db.Integer, default=0)

    forums = db.relationship('Forum')


forum_moderators = db.Table('forum_moderators',
    db.Column('forum_id', db.Integer, db.ForeignKey('forum.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')))


class Forum(db.Model, Base):
    __tablename__ = 'forum'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('forum_category.id'))
    name = db.Column(db.String(80))
    position = db.Column(db.Integer, default=0)
    description = db.Column(db.Text())
    updated = db.Column(db.DateTime, default=datetime.utcnow)
    post_count = db.Column(db.Integer, default=0)
    topic_count = db.Column(db.Integer, default=0)
    last_post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'))
    locked = db.Column(db.Boolean)

    category = db.relationship('ForumCategory')
    topics = db.relationship('ForumTopic')
    last_post = db.relationship('ForumPost')
    moderators = db.relationship('User', secondary=forum_moderators,
                                 backref=db.backref('moderated_forums'))

    @property
    def url(self):
        return url_for('forum', forum_id=self.id)


class ForumTopic(db.Model, Base):
    __tablename__ = 'forum_topic'

    id = db.Column(db.Integer, primary_key=True)
    forum_id = db.Column(db.Integer, db.ForeignKey('forum.id'))
    name = db.Column(db.String(255))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    views = db.Column(db.Integer, default=0)
    sticky = db.Column(db.Boolean, default=False)
    closed = db.Column(db.Boolean, default=False)
    deleted = db.Column(db.Boolean, default=False)
    post_count = db.Column(db.Integer, default=0)
    last_post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'))

    forum = db.relationship('Forum')
    user = db.relationship('User')
    posts = db.relationship('ForumPost', foreign_keys='ForumPost.topic_id')
    last_post = db.relationship('ForumPost', foreign_keys='ForumTopic.last_post_id')

    @property
    def replies(self):
        return self.post_count - 1

    @property
    def url(self):
        return url_for('forum_topic', topic_id=self.id)

    def update_read(self, user, commit=True):
        self.views +=1
        self.save(commit=True)

        tracking = user.posttracking

        if not tracking:
            return

        if tracking.last_read and (tracking.last_read > self.last_post.created):
            return

        topics = tracking.get_topics()

        if topics:
            if len(topics) > 5120:
                tracking.set_topics({})
                tracking.last_read = datetime.now()
                tracking.save(commit=commit)

            if self.last_post_id > topics.get(str(self.id), 0):
                topics[str(self.id)] = self.last_post_id
                tracking.set_topics(topics)
                tracking.save(commit=commit)
        else:
            tracking.set_topics({self.id: self.last_post_id})
            tracking.save(commit=commit)


class ForumPost(db.Model, Base):
    __tablename__ = 'forum_post'

    id = db.Column(db.Integer, primary_key=True)
    topic_id =  db.Column(db.Integer, db.ForeignKey('forum_topic.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime, default=None)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    markup = db.Column(db.String(15), default='bbcode')
    body = db.Column(db.Text())
    body_html = db.Column(db.Text())
    user_ip = db.Column(db.String(15))
    deleted = db.Column(db.Boolean, default=False)

    topic = db.relationship('ForumTopic', foreign_keys='ForumPost.topic_id')
    user = db.relationship('User', foreign_keys='ForumPost.user_id')
    updated_by = db.relationship('User', foreign_keys='ForumPost.updated_by_id')

    @property
    def url(self):
        return url_for('forum_post', post_id=self.id)

    def get_body_html(self, highlight=None):
        if highlight:
            return re.sub(r'(%s)' % re.escape(highlight),
                          r'<span class="search-match">\1</span>',
                          self.body_html, flags=re.IGNORECASE)

        return self.body_html

    def save(self, commit=True):
        from standardweb.lib import forums
        self.body_html = forums.convert_bbcode(self.body)

        for pat, path in forums.emoticon_map:
            self.body_html = pat.sub(path, self.body_html)

        return super(ForumPost, self).save(commit)


class ForumPostTracking(db.Model, Base):
    __tablename__ = 'forum_posttracking'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    topics =  db.Column(db.Text(), default=None)
    last_read = db.Column(db.DateTime, default=None)

    user = db.relationship('User', backref=db.backref('posttracking', uselist=False))

    def get_topics(self):
        return json.loads(self.topics) if self.topics else None

    def set_topics(self, topics):
        self.topics = json.dumps(topics)


class ForumAttachment(db.Model, Base):
    __tablename__ = 'forum_attachment'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'))
    size =  db.Column(db.Integer())
    content_type = db.Column(db.String(255))
    path = db.Column(db.String(255))
    name = db.Column(db.Text())
    hash = db.Column(db.String(40))

    post = db.relationship('ForumPost', backref=db.backref('attachments'))

    @classmethod
    def create_attachment(cls, post_id, image, commit=True):
        try:
            content_type = image.headers.get('Content-Type')
            image_content = image.content
            size = len(image_content)
            path = str(post_id)

            attachment = cls(post_id=post_id, size=size, content_type=content_type, path=path, name=image.filename)
            attachment.save(commit=commit)

            with open(attachment.file_path, 'w') as f:
                f.write(image_content)

            return attachment
        except:
            return None

    def save(self, commit=True):
        import hashlib

        self.hash = hashlib.sha1(self.path + app.config['SECRET_KEY']).hexdigest()

        return super(ForumAttachment, self).save(commit)

    @property
    def url(self):
        return url_for('forum_attachment', hash=self.hash)

    @property
    def file_path(self):
        return os.path.join(app.root_path, 'attachments', self.path)


class ForumBan(db.Model, Base):
    __tablename__ = 'forum_ban'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ban_start = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.Text())
    by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    user = db.relationship('User', foreign_keys='ForumBan.user_id', backref=db.backref('forum_ban', uselist=False))
    by_user = db.relationship('User', foreign_keys='ForumBan.by_user_id')
