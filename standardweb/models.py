from standardweb import db
from standardweb.lib import helpers as h

from pbkdf2 import pbkdf2_bin

from sqlalchemy.exc import IntegrityError

import binascii
import hashlib
import os


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


class User(db.Model, Base):
    __tablename__ = 'auth_user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30))
    email = db.Column(db.String(75))
    password = db.Column(db.String(128))
    is_superuser = db.Column(db.Boolean)

    def check_password(self, plaintext_password):
        algorithm, iterations, salt, hash_val = self.password.split('$', 3)
        expected = self._make_password(plaintext_password, salt=salt, iterations=int(iterations))

        return h.safe_str_cmp(self.password, expected)

    def set_password(self, plaintext_password, commit=True):
        password = self._make_password(plaintext_password)
        self.password = password
        self.save(commit=commit)

    def _make_password(self, password, salt=None, iterations=None):
        if not salt:
            salt = binascii.b2a_hex(os.urandom(15))

        if not iterations:
            iterations = 10000

        hash_val = pbkdf2_bin(bytes(password), bytes(salt), iterations, keylen=32, hashfunc=hashlib.sha256)
        hash_val = hash_val.encode('base64').strip()
        return '%s$%s$%s$%s' % ('pbkdf2_sha256', iterations, salt, hash_val)


class Player(db.Model, Base):
    __tablename__ = 'standardweb_minecraftplayer'

    id = db.Column(db.INTEGER, primary_key=True)
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
    def forum_profile(self):
        try:
            return self.djangobb_profile.get()
        except:
            return None

    @property
    def last_seen(self):
        return PlayerStats.objects.get(player=self, server=2).last_seen


class PlayerStats(db.Model, Base):
    __tablename__ = 'standardweb_playerstats'

    id = db.Column(db.INTEGER, primary_key=True)
    player_id = db.Column(db.INTEGER, db.ForeignKey('standardweb_minecraftplayer.id'))
    server_id = db.Column(db.INTEGER, db.ForeignKey('standardweb_server.id'))
    time_spent = db.Column(db.INTEGER)
    first_seen = db.Column(db.DATETIME)
    last_seen = db.Column(db.DATETIME)
    banned = db.Column(db.Boolean)
    pvp_logs = db.Column(db.INTEGER)

    def get_rank(self):
        return PlayerStats.query.filter(PlayerStats.server_id == self.server_id,
                                        PlayerStats.time_spent > self.time_spent,
                                        PlayerStats.player_id != self.player_id).count() + 1


class Server(db.Model, Base):
    __tablename__ = 'standardweb_server'

    id = db.Column(db.INTEGER, primary_key=True)
    name = db.Column(db.String(30))
    address = db.Column(db.String(50))
    secret_key = db.Column(db.String(10))


class DeathType(db.Model, Base):
    __tablename__ = 'standardweb_deathtype'

    id = db.Column(db.INTEGER, primary_key=True)
    type = db.Column(db.String(100))
    displayname = db.Column(db.String(100))


class KillType(db.Model, Base):
    __tablename__ = 'standardweb_killtype'

    id = db.Column(db.INTEGER, primary_key=True)
    type = db.Column(db.String(100))
    displayname = db.Column(db.String(100))


class DeathCount(db.Model, Base):
    __tablename__ = 'standardweb_deathcount'

    id = db.Column(db.INTEGER, primary_key=True)
    server_id = db.Column(db.INTEGER, db.ForeignKey('standardweb_server.id'))
    death_type_id = db.Column(db.INTEGER, db.ForeignKey('standardweb_deathtype.id'))
    victim_id = db.Column(db.INTEGER, db.ForeignKey('standardweb_minecraftplayer.id'))
    killer_id = db.Column(db.INTEGER, db.ForeignKey('standardweb_minecraftplayer.id'))
    count = db.Column(db.INTEGER)

    server = db.relationship('Server', foreign_keys='DeathCount.server_id')
    death_type = db.relationship('DeathType', foreign_keys='DeathCount.death_type_id')
    killer = db.relationship('Player', foreign_keys='DeathCount.killer_id')
    victim = db.relationship('Player', foreign_keys='DeathCount.victim_id')

    @classmethod
    def increment(cls, server, death_type, victim, killer):
        death_count, created = _get_or_create(cls, server=server,
                                              death_type=death_type,
                                              victim=victim,
                                              killer=killer)
        death_count.count += 1
        death_count.save()


class KillCount(db.Model, Base):
    __tablename__ = 'standardweb_killcount'

    id = db.Column(db.INTEGER, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('standardweb_server.id'))
    kill_type_id = db.Column(db.Integer, db.ForeignKey('standardweb_killtype.id'))
    killer_id = db.Column(db.INTEGER, db.ForeignKey('standardweb_minecraftplayer.id'))
    count = db.Column(db.INTEGER)

    server = db.relationship('Server', foreign_keys='KillCount.server_id')
    kill_type = db.relationship('KillType', foreign_keys='KillCount.kill_type_id')
    killer = db.relationship('Player', foreign_keys='KillCount.killer_id')

    @classmethod
    def increment(cls, server, kill_type, killer):
        kill_count, created = _get_or_create(cls, server=server,
                                             kill_type=kill_type,
                                             killer=killer)
        kill_count.count += 1
        kill_count.save()
