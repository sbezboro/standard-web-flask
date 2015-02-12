import hashlib
import hmac
import urllib

from flask import url_for
from markupsafe import Markup
from sqlalchemy.orm import joinedload
from voluptuous import All, Length, Required, Schema, Any

from standardweb import app
from standardweb.models import Player, User, ForumPost


KICKED_FROM_GROUP = 'kicked_from_group'
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
        Required('group_name'): All(basestring, Length(min=1))
    })

    def get_html_description(self, data):
        group_name = data['group_name']

        return Markup('You were kicked from the group <a href="%s">%s</a>' % (
            url_for('group', name=group_name), group_name
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
            return Markup('<a href="%s">%s</a> posted in the topic <a href="%s">%s</a>' % (
                url_for('player', username=player.username),
                player.displayname_html,
                url_for('forum_post', post_id=post.id),
                post.topic.name
            ))
        else:
            return Markup('%s posted in the topic <a href="%s">%s</a>' % (
                user.username,
                url_for('forum_post', post_id=post.id),
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
