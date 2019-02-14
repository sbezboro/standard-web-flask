import binascii
from datetime import datetime, timedelta
import hashlib
from operator import attrgetter
import os
import random
import string
from pbkdf2 import pbkdf2_bin
import pytz
import re
import uuid

from flask import json
from flask import url_for
from sqlalchemy.ext import mutable
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import backref
from sqlalchemy.sql import func

from standardweb import app
from standardweb import db
from standardweb.lib import helpers as h


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


class JsonEncodedDict(db.TypeDecorator):
    impl = db.String

    def process_bind_param(self, value, dialect):
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        return json.loads(value)

mutable.MutableDict.associate_with(JsonEncodedDict)


class Base(object):

    def __init__(self, **kwargs):
        super(Base, self).__init__()

    def save(self, commit=True):
        db.session.add(self)

        if commit:
            db.session.commit()

    def to_dict(self):
        raise NotImplementedError

    @classmethod
    def factory(cls, **kwargs):
        instance, created = _get_or_create(cls, **kwargs)

        return instance

    @classmethod
    def factory_and_created(cls, **kwargs):
        return _get_or_create(cls, **kwargs)


class User(db.Model, Base):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    uuid = db.Column(db.String(32))
    full_name = db.Column(db.String(50))
    email = db.Column(db.String(75))
    password = db.Column(db.String(128))
    admin = db.Column(db.Boolean, default=False)
    moderator = db.Column(db.Boolean, default=False)
    mfa_login = db.Column(db.Boolean, default=False)
    mfa_secret = db.Column(db.String(20))
    score = db.Column(db.Numeric(), default=0)
    last_login = db.Column(db.DateTime, default=None)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    session_key = db.Column(db.String(32))

    player = db.relationship('Player', backref=db.backref('user', uselist=False))

    @property
    def admin_or_moderator(self):
        return self.admin or self.moderator

    @classmethod
    def create(cls, player, plaintext_password, email):
        user = cls(player=player, uuid=player.uuid)
        user.set_password(plaintext_password)
        user.last_login = datetime.utcnow()
        user.email = email

        user.generate_session_key(commit=False)

        user.save(commit=False)

        forum_profile = ForumProfile(user=user)
        forum_profile.save(commit=True)

        # make sure messages/notifications received to this player are properly
        # associated with the newly created user
        Message.query.filter_by(
            to_player=player,
            to_user=None
        ).update({
            'to_user_id': user.id
        })

        Notification.query.filter_by(
            player=player,
            user=None
        ).update({
            'user_id': user.id
        })

        db.session.commit()

        return user

    def to_dict(self):
        result = {
            'username': self.username
        }

        if self.player_id:
            result['player'] = self.player.to_dict()

        return result

    def check_password(self, plaintext_password):
        algorithm, iterations, salt, hash_val = self.password.split('$', 3)
        expected = User._make_password(plaintext_password, salt=salt, iterations=int(iterations))

        return h.safe_str_cmp(self.password, expected)

    def set_password(self, plaintext_password, commit=True):
        password = User._make_password(plaintext_password)
        self.password = password
        self.save(commit=commit)

    def get_username(self):
        if self.player_id:
            return self.player.username

        return self.username

    def get_unread_notification_count(self):
        return len(
            Notification.query.with_entities(Notification.id).filter_by(
                user=self,
                seen_at=None
            ).all()
        )

    def get_unread_message_count(self):
        return len(
            Message.query.with_entities(Message.id).filter_by(
                to_user=self,
                seen_at=None,
                deleted=False
            ).all()
        )

    def get_notification_preferences(self, create=True, can_commit=True):
        from standardweb.lib import notifications

        preferences = NotificationPreference.query.filter_by(
            user=self
        ).all()

        if create:
            active_preference_names = set()
            for preference in preferences:
                active_preference_names.add(preference.name)

            missing_preference_names = notifications.NOTIFICATION_NAMES - active_preference_names
            for name in missing_preference_names:
                preference = NotificationPreference(
                    user=self,
                    name=name
                )

                preference.save(commit=False)

                preferences.append(preference)

            if can_commit:
                db.session.commit()

        return sorted(preferences, key=attrgetter('name'))

    def get_notification_preference(self, type, create=True, can_commit=True):
        preference = NotificationPreference.query.filter_by(
            user=self,
            name=type
        ).first()

        if not preference and create:
            preference = NotificationPreference(
                user=self,
                name=type
            )

            preference.save(commit=can_commit)

        return preference

    def generate_session_key(self, commit=True):
        self.session_key = ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(32))
        self.save(commit=commit)

    @property
    def has_excellent_score(self):
        return self.score > app.config['EXCELLENT_SCORE_THRESHOLD']

    @property
    def has_great_score(self):
        return self.score > app.config['GREAT_SCORE_THRESHOLD'] and not self.has_excellent_score

    @property
    def has_good_score(self):
        return self.score > app.config['GOOD_SCORE_THRESHOLD'] and not self.has_great_score

    @property
    def has_bad_score(self):
        return self.score < app.config['BAD_SCORE_THRESHOLD'] and not self.has_terrible_score

    @property
    def has_terrible_score(self):
        return self.score < app.config['TERRIBLE_SCORE_THRESHOLD'] and not self.has_abysmal_score

    @property
    def has_abysmal_score(self):
        return self.score < app.config['ABYSMAL_SCORE_THRESHOLD']


    @classmethod
    def _make_password(cls, password, salt=None, iterations=None):
        if not salt:
            salt = binascii.b2a_hex(os.urandom(15))

        if not iterations:
            iterations = 10000

        hash_val = pbkdf2_bin(password.encode('utf-8'), salt, iterations, keylen=32, hashfunc=hashlib.sha256)
        hash_val = hash_val.encode('base64').strip()
        return '%s$%s$%s$%s' % ('pbkdf2_sha256', iterations, salt, hash_val)


class EmailToken(db.Model, Base):
    __tablename__ = 'emailtoken'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32))
    type = db.Column(db.String(16))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    email = db.Column(db.String(75))
    uuid = db.Column(db.String(32))
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    date_redeemed = db.Column(db.DateTime, default=None)

    user = db.relationship('User')

    @classmethod
    def create_creation_token(cls, email, uuid, commit=True):
        et = cls(token=cls._generate_token(),
                 type='creation',
                 email=email,
                 uuid=uuid)
        et.save(commit=commit)

        return et

    @classmethod
    def create_verify_token(cls, email, user_id, commit=True):
        cls.query.filter_by(
            type='verify',
            email=email,
            date_redeemed=None
        ).delete()

        et = cls(token=cls._generate_token(),
                 type='verify',
                 email=email,
                 user_id=user_id)
        et.save(commit=commit)

        return et

    @classmethod
    def create_reset_password_token(cls, user_id, commit=True):
        et = cls(token=cls._generate_token(),
                 type='reset_password',
                 user_id=user_id)
        et.save(commit=commit)

        return et

    @classmethod
    def _generate_token(cls):
        import uuid
        return uuid.uuid4().hex


class Player(db.Model, Base):
    __tablename__ = 'player'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(32))
    username = db.Column(db.String(30))
    nickname = db.Column(db.String(30))
    nickname_ansi = db.Column(db.String(256))
    banned = db.Column(db.Boolean, default=False)

    def __str__(self):
        return self.displayname

    def to_dict(self):
        result = {
            'uuid': self.uuid,
            'username': self.username,
            'nickname': self.nickname,
            'nickname_html': self.nickname_html,
            'displayname': self.displayname,
            'displayname_html': self.displayname_html
        }

        return result

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
    def past_usernames(self):
        logs = self.audit_logs.filter_by(type='player_rename')

        return list(set([
            log.data['old_name'] for log in logs
        ]))

    @property
    def display_uuid(self):
        return str(uuid.UUID(self.uuid))

    def set_username(self, new_username):
        AuditLog.create(
            AuditLog.PLAYER_RENAME,
            player_id=self.id,
            old_name=self.username,
            new_name=new_username,
            commit=False
        )

        self.username = new_username

    def adjust_time_spent(self, server, adjustment, reason=None, commit=True):
        stat = PlayerStats.query.filter_by(
            player=self,
            server=server
        ).first()

        if stat:
            stat.adjust_time_spent(adjustment, reason=reason, commit=commit)


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
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    is_leader = db.Column(db.Boolean, default=False)
    is_moderator = db.Column(db.Boolean, default=False)

    server = db.relationship('Server')
    player = db.relationship('Player')
    group = db.relationship('Group')

    @property
    def is_online(self):
        return datetime.utcnow() - self.last_seen < timedelta(minutes=1)

    @property
    def rank(self):
        return len(
            PlayerStats.query.with_entities(
                PlayerStats.id
            ).filter(
                PlayerStats.server_id == self.server_id,
                PlayerStats.time_spent > self.time_spent,
                PlayerStats.player_id != self.player_id
            ).all()
        ) + 1

    def adjust_time_spent(self, adjustment, reason=None, commit=True):
        self.time_spent += adjustment
        self.save(commit=False)

        AuditLog.create(
            AuditLog.PLAYER_TIME_ADJUSTMENT,
            server_id=self.server_id,
            player_id=self.player_id,
            adjustment=adjustment,
            reason=reason,
            commit=commit
        )


class Server(db.Model, Base):
    __tablename__ = 'server'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30))
    abbreviation = db.Column(db.String(10))
    address = db.Column(db.String(50))
    online = db.Column(db.Boolean())
    secret_key = db.Column(db.String(64))
    type = db.Column(db.String(20))

    @classmethod
    def get_survival_servers(cls):
        return cls.query.filter_by(type='survival')


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

    ORES = (
        'DIAMOND_ORE', 'EMERALD_ORE', 'LAPIS_ORE', 'REDSTONE_ORE', 'NETHER_QUARTZ_ORE', 'COAL_ORE'
    )

    @classmethod
    def get_ores(cls):
        return cls.query.filter(
            cls.type.in_(cls.ORES)
        ).order_by(func.field(cls.type, *cls.ORES))


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
        ore_count = cls.factory(
            server=server,
            material_type=material_type,
            player=player
        )
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


class Group(db.Model, Base):
    __tablename__ = 'group'

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    uid = db.Column(db.String(32))
    name = db.Column(db.String(20))
    established = db.Column(db.DateTime)
    land_count = db.Column(db.Integer)
    land_limit = db.Column(db.Integer)
    member_count = db.Column(db.Integer)
    lock_count = db.Column(db.Integer)

    server = db.relationship('Server')
    members = db.relationship(
        'Player',
        secondary='join(PlayerStats, Player, PlayerStats.player_id == Player.id)',
        primaryjoin='Group.id == PlayerStats.group_id',
        secondaryjoin='PlayerStats.player_id == Player.id'
    )


class GroupInvite(db.Model, Base):
    __tablename__ = 'group_invite'

    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), primary_key=True)
    invite = db.Column(db.String(30), primary_key=True)

    group = db.relationship('Group', backref=db.backref('invites'))


player_title = db.Table('player_title',
    db.Column('player_id', db.Integer, db.ForeignKey('player.id')),
    db.Column('title_id', db.Integer, db.ForeignKey('title.id')))


class Title(db.Model, Base):
    __tablename__ = 'title'

    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    name = db.Column(db.String(20))
    displayname = db.Column(db.String(40))
    broadcast = db.Column(db.Boolean, default=False)

    players = db.relationship('Player', secondary=player_title,
                              backref=db.backref('titles'))


class VeteranStatus(db.Model, Base):
    __tablename__ = 'veteranstatus'

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    rank = db.Column(db.Integer)

    server = db.relationship('Server')
    player = db.relationship('Player')


class Message(db.Model, Base):
    __tablename__ = 'message'

    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    seen_at = db.Column(db.DateTime)
    notified_at = db.Column(db.DateTime)
    body = db.Column(db.Text())
    body_html = db.Column(db.Text())
    user_ip = db.Column(db.String(15))
    deleted = db.Column(db.Boolean, default=False)

    from_user = db.relationship('User', foreign_keys='Message.from_user_id',
                                backref=db.backref('messages_sent'))
    to_user = db.relationship('User', foreign_keys='Message.to_user_id',
                              backref=db.backref('messages_received'))
    to_player = db.relationship('Player', foreign_keys='Message.to_player_id',
                                backref=db.backref('messages_received'))

    def save(self, commit=True):
        from standardweb.lib import forums
        self.body_html = forums.convert_bbcode(self.body)

        for pat, path in forums.emoticon_map:
            self.body_html = pat.sub(path, self.body_html)

        return super(Message, self).save(commit)

    def to_dict(self):
        result = {
            'id': self.id,
            'sent_at': self.sent_at.replace(tzinfo=pytz.UTC).isoformat(),
            'seen_at': self.seen_at.replace(tzinfo=pytz.UTC).isoformat() if self.seen_at else None,
            'from_user': self.from_user.to_dict(),
            'body_html': self.body_html
        }

        if self.to_user:
            result['to_user'] = self.to_user.to_dict()

        return result


class Notification(db.Model, Base):
    __tablename__ = 'notification'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    type = db.Column(db.String(30))
    seen_at = db.Column(db.DateTime)
    data = db.Column(JsonEncodedDict, default={})

    user = db.relationship(
        'User',
        foreign_keys='Notification.user_id',
        backref=db.backref('notifications')
    )

    player = db.relationship(
        'Player',
        foreign_keys='Notification.player_id',
        backref=db.backref('notifications')
    )

    _definition = None

    @classmethod
    def create(cls, type, data=None, user_id=None, player_id=None, send_email=True, **kw):
        from standardweb.lib import notifier

        if data is None:
            data = {}

        data.update(**kw)

        notification = cls(
            type=type,
            user_id=user_id,
            player_id=player_id,
            data=data
        )

        notification.definition
        notification.save(commit=True)

        notifier.notification_notify(notification, send_email=send_email)

        return notification

    @property
    def definition(self):
        from standardweb.lib import notifications

        if not self._definition:
            self._definition = notifications.validate_notification(self.type, self.data)

        return self._definition

    @property
    def description(self):
        return self.definition.get_html_description(self.data)

    @property
    def can_notify_ingame(self):
        return self.definition.can_notify_ingame


class AccessLog(db.Model, Base):
    __tablename__ = 'access_log'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    client_uuid = db.Column(db.String(36))
    method = db.Column(db.String(10))
    route = db.Column(db.String(40))
    request_path = db.Column(db.String(1000))
    request_referrer = db.Column(db.String(1000))
    response_code = db.Column(db.Integer)
    response_time = db.Column(db.Integer)
    user_agent = db.Column(db.String(1000))
    ip_address = db.Column(db.String(15))

    user = db.relationship('User')


class AuditLog(db.Model, Base):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    type = db.Column(db.String(32))
    data = db.Column(JsonEncodedDict, default={})

    server = db.relationship('Server')
    user = db.relationship('User')
    player = db.relationship(
        'Player',
        backref=backref(
            'audit_logs',
            lazy='dynamic'
        )
    )

    PLAYER_TIME_ADJUSTMENT = 'player_time_adjustment'
    PLAYER_RENAME = 'player_rename'
    PLAYER_BAN = 'player_ban'
    PLAYER_UNBAN = 'player_unban'
    QUICK_USER_CREATE = 'quick_user_create'
    INVALID_LOGIN = 'invalid_login'
    USER_FORUM_BAN = 'user_forum_ban'
    USER_FORUM_UNBAN = 'user_forum_unban'

    @classmethod
    def create(cls, type, data=None, server_id=None, user_id=None, player_id=None, commit=True, **kw):
        if data is None:
            data = {}

        data.update(**kw)

        audit_log = cls(
            type=type,
            server_id=server_id,
            user_id=user_id,
            player_id=player_id,
            data=data
        )

        audit_log.save(commit=commit)
        return audit_log


class NotificationPreference(db.Model, Base):
    __tablename__ = 'notification_preference'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    name = db.Column(db.String(64), primary_key=True)
    email = db.Column(db.Boolean, default=True)
    ingame = db.Column(db.Boolean, default=True)

    user = db.relationship('User')

    @property
    def description(self):
        from standardweb.lib import notifications
        return notifications.get_setting_description(self.name)

    @property
    def definition(self):
        from standardweb.lib import notifications
        return notifications.NOTIFICATION_DEFINITIONS[self.name]


class ForumProfile(db.Model, Base):
    __tablename__ = 'forum_profile'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_count = db.Column(db.Integer, default=0)
    signature = db.Column(db.Text())
    signature_html = db.Column(db.Text())

    user = db.relationship('User', backref=db.backref('forum_profile', uselist=False))

    @property
    def last_post(self):
        post = ForumPost.query.filter(
            ForumPost.deleted == False,
            ForumPost.user_id == self.user_id
        ).order_by(
            ForumPost.created.desc()
        ).limit(1).first()

        return post


class ForumCategory(db.Model, Base):
    __tablename__ = 'forum_category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    position = db.Column(db.Integer, default=0)
    collapsed = db.Column(db.Boolean, default=False)

    forums = db.relationship('Forum')


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
            tracking.last_read = datetime.now()
            tracking.set_topics({self.id: self.last_post_id})
            tracking.save(commit=commit)


class ForumPost(db.Model, Base):
    __tablename__ = 'forum_post'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topic.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime, default=None)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    body = db.Column(db.Text())
    body_html = db.Column(db.Text())
    user_ip = db.Column(db.String(15))
    score = db.Column(db.Numeric(), default=0)
    deleted = db.Column(db.Boolean, default=False)

    topic = db.relationship('ForumTopic', foreign_keys='ForumPost.topic_id')
    user = db.relationship('User', foreign_keys='ForumPost.user_id')
    updated_by = db.relationship('User', foreign_keys='ForumPost.updated_by_id')

    @property
    def url(self):
        return url_for('forum_post', post_id=self.id)

    @property
    def is_bad(self):
        return self.score < app.config['BAD_POST_THRESHOLD']

    @property
    def grouped_votes(self):
        from standardweb.lib import forums
        return forums.grouped_votes(self.votes)

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


class ForumPostVote(db.Model, Base):
    __tablename__ = 'forum_post_vote'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'))
    vote = db.Column(db.Integer(), default=0)
    user_ip = db.Column(db.String(15))
    computed_weight = db.Column(db.Numeric())
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime, default=None)

    post = db.relationship('ForumPost', backref=db.backref('votes'))
    user = db.relationship('User', backref=db.backref('votes'))


class ForumPostTracking(db.Model, Base):
    __tablename__ = 'forum_posttracking'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    topics =  db.Column(db.Text(), default=None)
    last_read = db.Column(db.DateTime, default=None)

    user = db.relationship('User', backref=db.backref('posttracking', uselist=False))

    def get_topics(self):
        try:
            return json.loads(self.topics) if self.topics else None
        except ValueError:
            return None

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


class ForumTopicSubscription(db.Model, Base):
    __tablename__ = 'forum_topic_subscription'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topic.id'), primary_key=True)

    user = db.relationship('User')
    topic = db.relationship('ForumTopic')
