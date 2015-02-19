import hashlib
import hmac
import urllib
from datetime import datetime

from flask import url_for
from markupsafe import Markup
from sqlalchemy.orm import joinedload
from voluptuous import All, Length, Required, Schema, Any, Optional

from standardweb import app, db
from standardweb.models import Player, User, ForumPost, Notification


KICKED_FROM_GROUP = 'kicked_from_group'
GROUP_KICK_IMMINENT = 'group_kick_imminent'
GROUP_DESTROYED = 'group_destroyed'
NEW_GROUP_MEMBER = 'new_group_member'
GROUP_LAND_LIMIT_GROWTH = 'group_land_limit_growth'
NEWS_POST = 'news'
SUBSCRIBED_TOPIC_POST = 'subscribed_thread_post'

NOTIFICATION_DEFINITIONS = {}


class InvalidNotificationError(RuntimeError):
    pass


class NotificationDefinition(object):

    name = None
    schema = None
    should_notify_ingame = False

    def __init__(self):
        if not self.name:
            raise NotImplementedError('Notification must define a name')

        if not self.schema:
            raise NotImplementedError('Notification must define a schema')

        NOTIFICATION_DEFINITIONS[self.name] = self

    def get_html_description(self, data):
        raise NotImplementedError('Notification must implement an html description')


class KickedFromGroupNotification(NotificationDefinition):

    name = KICKED_FROM_GROUP
    schema = Schema({
        Required('group_name'): All(basestring, Length(min=1)),
        Optional('kicker_uuid'): All(basestring, Length(min=32, max=32))
    })

    def get_html_description(self, data):
        group_name = data['group_name']
        kicker_uuid = data.get('kicker_uuid')

        if kicker_uuid:
            kicker = Player.query.filter_by(uuid=kicker_uuid).first()

            return Markup('You were kicked from the group <a href="%s">%s</a> by <a href="%s">%s</a>' % (
                url_for('group', name=group_name),
                group_name,
                url_for('player', username=kicker.username),
                kicker.displayname_html,
            ))
        else:
            return Markup('You were automatically kicked from the group <a href="%s">%s</a> after being offline too long' % (
                url_for('group', name=group_name), group_name
            ))


class GroupKickImminentNotification(NotificationDefinition):

    name = GROUP_KICK_IMMINENT
    schema = Schema({
        Required('group_name'): All(basestring, Length(min=1))
    })

    def get_html_description(self, data):
        group_name = data['group_name']

        return Markup('You will be automatically kicked from your group <a href="%s">%s</a> in <b>one</b> day if you don\'t join the server!' % (
            url_for('group', name=group_name),
            group_name
        ))


class GroupDestroyedNotification(NotificationDefinition):

    name = GROUP_DESTROYED
    schema = Schema({
        Required('group_name'): All(basestring, Length(min=1)),
        Optional('destroyer_uuid'): All(basestring, Length(min=32, max=32))
    })

    def get_html_description(self, data):
        group_name = data['group_name']

        destroyer_uuid = data.get('destroyer_uuid')

        if destroyer_uuid:
            destroyer = Player.query.filter_by(uuid=destroyer_uuid).first()

            return Markup('Your group %s was destroyed by <a href="%s">%s</a>' % (
                group_name,
                url_for('player', username=destroyer.username),
                destroyer.displayname_html,
            ))
        else:
            return Markup('Your group %s was automatically destroyed' % (
                group_name
            ))


class NewGroupMemberNotification(NotificationDefinition):

    name = NEW_GROUP_MEMBER
    schema = Schema({
        Required('group_name'): All(basestring, Length(min=1)),
        Required('player_uuid'): All(basestring, Length(min=32, max=32)),
        Required('inviter_uuid'): All(basestring, Length(min=32, max=32))
    })

    def get_html_description(self, data):
        group_name = data['group_name']
        player_uuid = data['player_uuid']
        inviter_uuid = data['inviter_uuid']
        player = Player.query.filter_by(uuid=player_uuid).first()
        inviter = Player.query.filter_by(uuid=inviter_uuid).first()

        return Markup('<a href="%s">%s</a> joined your group <a href="%s">%s</a> after being invited by <a href="%s">%s</a>' % (
            url_for('player', username=player.username),
            player.displayname_html,
            url_for('group', name=group_name),
            group_name,
            url_for('player', username=inviter.username),
            inviter.displayname_html,
        ))


class GroupLandLimitGrowthNotification(NotificationDefinition):

    name = GROUP_LAND_LIMIT_GROWTH
    schema = Schema({
        Required('group_name'): All(basestring, Length(min=1)),
        Required('amount'): Any(long, int),
        Required('new_limit'): Any(long, int)
    })

    def get_html_description(self, data):
        group_name = data['group_name']
        amount = data['amount']
        new_limit = data['new_limit']

        return Markup('Your group <a href="%s">%s</a> gained %d additional land resulting in a new limit of %d' % (
            url_for('group', name=group_name),
            group_name,
            amount,
            new_limit
        ))


class NewsPostNotification(NotificationDefinition):

    name = NEWS_POST
    schema = Schema({
        Required('post_id'): Any(long, int)
    })

    def get_html_description(self, data):
        post_id = data['post_id']

        post = ForumPost.query.options(
            joinedload(ForumPost.topic)
        ).get(post_id)

        return Markup('<a href="%s">%s</a>' % (
            url_for('forum_topic', topic_id=post.topic_id),
            post.topic.name
        ))


class SubscribedTopicPostNotification(NotificationDefinition):

    name = SUBSCRIBED_TOPIC_POST
    schema = Schema({
        Required('post_id'): Any(long, int)
    })

    def get_html_description(self, data):
        post_id = data['post_id']

        post = ForumPost.query.options(
            joinedload(ForumPost.topic)
        ).options(
            joinedload(ForumPost.user)
            .joinedload(User.player)
        ).get(post_id)

        user = post.user
        player = user.player

        if player:
            return Markup('<a href="%s">%s</a> <a href="%s">posted</a> in the topic <a href="%s">%s</a>' % (
                url_for('player', username=player.username),
                player.displayname_html,
                url_for('forum_post', post_id=post.id),
                url_for('forum_topic', topic_id=post.topic_id),
                post.topic.name
            ))
        else:
            return Markup('%s <a href="%s">posted</a> in the topic <a href="%s">%s</a>' % (
                user.username,
                url_for('forum_post', post_id=post.id),
                url_for('forum_topic', topic_id=post.topic_id),
                post.topic.name
            ))


for name, value in globals().items():
    if (
        isinstance(value, type)
        and issubclass(value, NotificationDefinition)
        and value != NotificationDefinition
    ):
        value()


def validate_notification(type, data):
    definition = NOTIFICATION_DEFINITIONS.get(type)

    if not definition:
        raise InvalidNotificationError()

    definition.schema(data)

    return definition


def _generate_signature(encoded_email, type):
    return hmac.new(
        app.config['UNSUBSCRIBE_SECRET'],
        msg='%s/%s' % (encoded_email, type),
        digestmod=hashlib.sha256
    ).hexdigest()


def verify_unsubscribe_request(encoded_email, type, signature):
    expected_signature = _generate_signature(encoded_email, type)

    return signature == expected_signature


def generate_unsubscribe_link(user, type):
    encoded_email = urllib.quote(user.email)
    signature = _generate_signature(encoded_email, type)

    return url_for('unsubscribe', encoded_email=encoded_email, type=type, signature=signature, _external=True)


def mark_notifications_read(user, key_values, allow_commit=True):
    notifications = Notification.query.filter_by(
        user=user,
        seen_at=None
    )

    updated = False
    for notification in notifications:
        # check the list of key values against the notification's data
        for kw in key_values:
            # if a key value matches this notification, mark it as read
            # and continue to the next notification
            if all(notification.data.get(k) == v for k, v in kw.iteritems()):
                notification.seen_at = datetime.utcnow()
                notification.save(commit=False)
                updated = True
                break

    if allow_commit and updated:
        db.session.commit()
