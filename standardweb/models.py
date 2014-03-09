from flask import url_for

from standardweb import db
from standardweb.lib import helpers as h

from pbkdf2 import pbkdf2_bin

from sqlalchemy.exc import IntegrityError

from datetime import datetime

import binascii
import hashlib
import os


def _get_or_create(cls, commit=True, **kwargs):
    query = cls.query.filter_by(**kwargs)

    instance = query.first()

    if instance:
        return instance, False
    else:
        db.session.begin(nested=True)
        try:
            instance = cls(**kwargs)

            db.session.add(instance)
            if commit:
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
    def factory(cls, commit=True, **kwargs):
        instance, created = _get_or_create(cls, commit=commit, **kwargs)

        return instance


class User(db.Model, Base):
    __tablename__ = 'auth_user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30))
    email = db.Column(db.String(75))
    password = db.Column(db.String(128))
    is_superuser = db.Column(db.Boolean)

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
    __tablename__ = 'standardweb_minecraftplayer'

    id = db.Column(db.Integer, primary_key=True)
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

    @property
    def last_seen(self):
        return PlayerStats.objects.get(player=self, server=2).last_seen


class PlayerStats(db.Model, Base):
    __tablename__ = 'standardweb_playerstats'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('standardweb_minecraftplayer.id'))
    server_id = db.Column(db.Integer, db.ForeignKey('standardweb_server.id'))
    time_spent = db.Column(db.Integer)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    banned = db.Column(db.Boolean)
    pvp_logs = db.Column(db.Integer)

    server = db.relationship('Server', foreign_keys='PlayerStats.server_id')
    player = db.relationship('Player', foreign_keys='PlayerStats.player_id')

    def get_rank(self):
        return PlayerStats.query.filter(PlayerStats.server_id == self.server_id,
                                        PlayerStats.time_spent > self.time_spent,
                                        PlayerStats.player_id != self.player_id).count() + 1


class Server(db.Model, Base):
    __tablename__ = 'standardweb_server'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30))
    address = db.Column(db.String(50))
    secret_key = db.Column(db.String(10))


class ServerStatus(db.Model, Base):
    __tablename__ = 'standardweb_serverstatus'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    server_id = db.Column(db.Integer, db.ForeignKey('standardweb_server.id'))
    player_count = db.Column(db.Integer)
    cpu_load = db.Column(db.Float)
    tps = db.Column(db.Float)

    server = db.relationship('Server', foreign_keys='ServerStatus.server_id')


class MojangStatus(db.Model, Base):
    __tablename__ = 'standardweb_mojangstatus'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    website = db.Column(db.Boolean)
    login = db.Column(db.Boolean)
    session = db.Column(db.Boolean)
    account = db.Column(db.Boolean)
    auth = db.Column(db.Boolean)
    skins = db.Column(db.Boolean)


class DeathType(db.Model, Base):
    __tablename__ = 'standardweb_deathtype'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100))
    displayname = db.Column(db.String(100))


class KillType(db.Model, Base):
    __tablename__ = 'standardweb_killtype'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100))
    displayname = db.Column(db.String(100))


class DeathCount(db.Model, Base):
    __tablename__ = 'standardweb_deathcount'

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('standardweb_server.id'))
    death_type_id = db.Column(db.Integer, db.ForeignKey('standardweb_deathtype.id'))
    victim_id = db.Column(db.Integer, db.ForeignKey('standardweb_minecraftplayer.id'))
    killer_id = db.Column(db.Integer, db.ForeignKey('standardweb_minecraftplayer.id'))
    count = db.Column(db.Integer)

    server = db.relationship('Server', foreign_keys='DeathCount.server_id')
    death_type = db.relationship('DeathType', foreign_keys='DeathCount.death_type_id')
    killer = db.relationship('Player', foreign_keys='DeathCount.killer_id')
    victim = db.relationship('Player', foreign_keys='DeathCount.victim_id')

    @classmethod
    def increment(cls, server, death_type, victim, killer):
        death_count = cls.factory(server=server,
                                  death_type=death_type,
                                  victim=victim,
                                  killer=killer)
        death_count.count += 1
        death_count.save()


class KillCount(db.Model, Base):
    __tablename__ = 'standardweb_killcount'

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('standardweb_server.id'))
    kill_type_id = db.Column(db.Integer, db.ForeignKey('standardweb_killtype.id'))
    killer_id = db.Column(db.Integer, db.ForeignKey('standardweb_minecraftplayer.id'))
    count = db.Column(db.Integer)

    server = db.relationship('Server', foreign_keys='KillCount.server_id')
    kill_type = db.relationship('KillType', foreign_keys='KillCount.kill_type_id')
    killer = db.relationship('Player', foreign_keys='KillCount.killer_id')

    @classmethod
    def increment(cls, server, kill_type, killer):
        kill_count = cls.factory(server=server,
                                 kill_type=kill_type,
                                 killer=killer)
        kill_count.count += 1
        kill_count.save()


class MaterialType(db.Model, Base):
    __tablename__ = 'standardweb_materialtype'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(32), unique=True)
    displayname = db.Column(db.String(64))


class OreDiscoveryEvent(db.Model, Base):
    __tablename__ = 'standardweb_orediscoveryevent'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    server_id = db.Column(db.Integer, db.ForeignKey('standardweb_server.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('standardweb_minecraftplayer.id'))
    material_type_id = db.Column(db.Integer, db.ForeignKey('standardweb_materialtype.id'))
    x = db.Column(db.Integer)
    y = db.Column(db.Integer)
    z = db.Column(db.Integer)

    server = db.relationship('Server', foreign_keys='OreDiscoveryEvent.server_id')
    player = db.relationship('Player', foreign_keys='OreDiscoveryEvent.player_id')
    material_type = db.relationship('MaterialType', foreign_keys='OreDiscoveryEvent.material_type_id')


class OreDiscoveryCount(db.Model, Base):
    __tablename__ = 'standardweb_orediscoverycount'

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('standardweb_server.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('standardweb_minecraftplayer.id'))
    material_type_id = db.Column(db.Integer, db.ForeignKey('standardweb_materialtype.id'))
    count = db.Column(db.Integer, default=0)

    server = db.relationship('Server', foreign_keys='OreDiscoveryCount.server_id')
    player = db.relationship('Player', foreign_keys='OreDiscoveryCount.player_id')
    material_type = db.relationship('MaterialType', foreign_keys='OreDiscoveryCount.material_type_id')

    @classmethod
    def increment(cls, server, material_type, player):
        ore_count, created = cls.factory(server=server,
                                         material_type=material_type,
                                         player=player)
        ore_count.count += 1
        ore_count.save()


class ForumCategory(db.Model, Base):
    __tablename__ = 'djangobb_forum_category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    position = db.Column(db.Integer, default=0)

    forums = db.relationship('Forum')


class Forum(db.Model, Base):
    __tablename__ = 'djangobb_forum_forum'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('djangobb_forum_category.id'))
    name = db.Column(db.String(80))
    position = db.Column(db.Integer, default=0)
    description = db.Column(db.Text())
    updated = db.Column(db.DateTime, default=datetime.utcnow)
    post_count = db.Column(db.Integer, default=0)
    topic_count = db.Column(db.Integer, default=0)
    last_post_id = db.Column(db.Integer, db.ForeignKey('djangobb_forum_post.id'))
    locked = db.Column(db.Boolean)

    category = db.relationship('ForumCategory', foreign_keys='Forum.category_id')
    topics = db.relationship('ForumTopic')
    last_post = db.relationship('ForumPost', foreign_keys='Forum.last_post_id')

    @property
    def url(self):
        return url_for('forum', forum_id=self.id)


class ForumTopic(db.Model, Base):
    __tablename__ = 'djangobb_forum_topic'

    id = db.Column(db.Integer, primary_key=True)
    forum_id = db.Column(db.Integer, db.ForeignKey('djangobb_forum_forum.id'))
    name = db.Column(db.String(255))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime, default=None)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'))
    views = db.Column(db.Integer, default=0)
    sticky = db.Column(db.Boolean)
    closed = db.Column(db.Boolean)
    post_count = db.Column(db.Integer)
    last_post_id = db.Column(db.Integer, db.ForeignKey('djangobb_forum_post.id'))

    forum = db.relationship('Forum', foreign_keys='ForumTopic.forum_id')
    user = db.relationship('User', foreign_keys='ForumTopic.user_id')
    posts = db.relationship('ForumPost', foreign_keys='ForumPost.topic_id')
    last_post = db.relationship('ForumPost', foreign_keys='ForumTopic.last_post_id')

    @property
    def url(self):
        return url_for('forum_topic', topic_id=self.id)


class ForumPost(db.Model, Base):
    __tablename__ = 'djangobb_forum_post'

    id = db.Column(db.Integer, primary_key=True)
    topic_id =  db.Column(db.Integer, db.ForeignKey('djangobb_forum_topic.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime, default=None)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'))
    body = db.Column(db.Text())
    body_html = db.Column(db.Text())
    user_ip = db.Column(db.String(15))

    topic = db.relationship('ForumTopic', foreign_keys='ForumPost.topic_id')
    user = db.relationship('User', foreign_keys='ForumPost.user_id')

    @property
    def url(self):
        return url_for('forum_post', post_id=self.id)


class ForumPostTracking(db.Model, Base):
    __tablename__ = 'djangobb_forum_posttracking'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'))
    topics =  db.Column(db.Text())
    last_read = db.Column(db.DateTime, default=None)

    user = db.relationship('User', foreign_keys='ForumPostTracking.user_id',
                           backref=db.backref('posttracking', lazy='joined'))
