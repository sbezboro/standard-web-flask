import bbcode

import cgi
import re

from standardweb import app, db
from standardweb.lib import player as libplayer
from standardweb.models import AuditLog, ForumTopicSubscription, ForumTopic, ForumPost, Forum


_bbcode_parser = bbcode.Parser()

_emoticon_map = {
    ':\)': 'emoticons/smile.png',
    ':angel:': 'emoticons/angel.png',
    ':angry:': 'emoticons/angry.png',
    '8-\)': 'emoticons/cool.png',
    ":'\(": 'emoticons/cwy.png',
    ':ermm:': 'emoticons/ermm.png',
    ':D': 'emoticons/grin.png',
    '<3': 'emoticons/heart.png',
    ':\(': 'emoticons/sad.png',
    ':O': 'emoticons/shocked.png',
    ':P': 'emoticons/tongue.png',
    ';\)': 'emoticons/wink.png',
    ':alien:': 'emoticons/alien.png',
    ':blink:': 'emoticons/blink.png',
    ':blush:': 'emoticons/blush.png',
    ':cheerful:': 'emoticons/cheerful.png',
    ':devil:': 'emoticons/devil.png',
    ':dizzy:': 'emoticons/dizzy.png',
    ':getlost:': 'emoticons/getlost.png',
    ':happy:': 'emoticons/happy.png',
    ':kissing:': 'emoticons/kissing.png',
    ':ninja:': 'emoticons/ninja.png',
    ':pinch:': 'emoticons/pinch.png',
    ':pouty:': 'emoticons/pouty.png',
    ':sick:': 'emoticons/sick.png',
    ':sideways:': 'emoticons/sideways.png',
    ':silly:': 'emoticons/silly.png',
    ':sleeping:': 'emoticons/sleeping.png',
    ':unsure:': 'emoticons/unsure.png',
    ':woot:': 'emoticons/w00t.png',
    ':wassat:': 'emoticons/wassat.png'
}

emoticon_map = [
    (re.compile(cgi.escape(k)), '<img src="https://%s%s"/>' % (app.config['CDN_DOMAIN'], '/static/images/forums/' + v))
    for k, v in _emoticon_map.iteritems()
]


def convert_bbcode(text):
    return _bbcode_parser.format(text)


def _render_size(tag_name, value, options, parent, context):
    size = 1

    if 'size' in options:
        size = options['size']
    elif len(options) == 1:
        key, val = options.items()[0]

        if val:
            size = val
        elif key:
            size = key

    return '<font size="%s">%s</font>' % (size, value)


def _render_quote(tag_name, value, options, parent, context):
    name = options.get('quote')
    if name:
        return '<blockquote><span class="quote-username">%s</span>%s</blockquote>' % (name, value)

    return '<blockquote>%s</blockquote>' % value


def subscribe_to_topic(user, topic, commit=True):
    subscription = ForumTopicSubscription(
        user=user,
        topic=topic
    )

    subscription.save(commit=False)

    AuditLog.create('topic_subscribe', user_id=user.id, data={
        'topic_id': topic.id
    }, commit=commit)


def should_notify_post(user, topic, post):
    return (
        not topic.forum.category.collapsed and
        user.score > app.config['BAD_SCORE_THRESHOLD']
    )


def grouped_votes(votes):
    up_list = []
    down_list = []

    for vote in votes:
        if vote.vote == 1:
            up_list.append(vote)
        elif vote.vote == -1:
            down_list.append(vote)

    return {
        'up_list': up_list,
        'down_list': down_list
    }


def can_user_post(user):
    if not user:
        return False

    if not user.player:
        return True

    total_time = libplayer.get_total_player_time(user.player.id)

    return total_time > app.config['MINIMUM_FORUM_POST_PLAYER_TIME']


def delete_post(post):
    first_post = ForumPost.query.join(ForumPost.topic) \
        .filter(ForumTopic.id == post.topic_id) \
        .order_by(ForumPost.created).first()

    post.deleted = True
    post.save(commit=True)

    # if its the first post being deleted, this means the topic will be deleted
    # as well, so reduce the post count for every user in the topic
    if post.id == first_post.id:
        posts = ForumPost.query.join(ForumPost.topic) \
            .filter(ForumPost.deleted == False, ForumTopic.id == post.topic_id)

        for other_post in posts:
            other_post.deleted = True
            other_post.save(commit=False)

            other_post.user.forum_profile.post_count -= 1
            other_post.user.forum_profile.save(commit=False)

            other_post.topic.forum.post_count -= 1

        post.topic.forum.topic_count -= 1
        post.topic.forum.save(commit=False)

        post.topic.post_count = 0
        post.topic.deleted = True

        # commit so the queries below will work properly
        post.topic.save(commit=True)

    # otherwise if this is the last post in the topic, update the topic's last
    # post pointer to be the next latest post in the topic
    elif post.id == post.topic.last_post_id:
        new_last_post = ForumPost.query.join(ForumPost.topic) \
            .filter(ForumPost.deleted == False, ForumTopic.id == post.topic_id) \
            .order_by(ForumPost.created.desc()).first()

        post.topic.last_post = new_last_post
        post.topic.updated = new_last_post.created
        post.topic.save(commit=False)

    # if this is the last post for the forum, or the topic is being deleted and the topic
    # is the last topic of the forum, update the forum's last post pointer to be
    # the next latest post in the forum
    if (post == first_post and post.topic.last_post_id == post.topic.forum.last_post_id) or \
                    post.id == post.topic.forum.last_post_id:
        new_last_post = ForumPost.query.join(ForumPost.topic).join(ForumTopic.forum) \
            .filter(ForumPost.deleted == False, Forum.id == post.topic.forum_id) \
            .order_by(ForumPost.created.desc()).first()

        post.topic.forum.last_post = new_last_post
        post.topic.forum.save(commit=False)

    post.user.forum_profile.post_count -= 1
    post.user.forum_profile.save(commit=False)

    post.topic.forum.post_count -= 1
    post.topic.forum.save(commit=False)

    if post.topic.post_count > 0:
        post.topic.post_count -= 1
        post.topic.save(commit=False)

    db.session.commit()


_bbcode_parser.add_simple_formatter(
    'img',
    '<img src="%(value)s"/>',
    replace_links=False,
    replace_cosmetic=False
)
_bbcode_parser.add_simple_formatter(
    'youtube',
    '<iframe width="516" height="315" src="//www.youtube.com/embed/%(value)s" frameborder="0" allowfullscreen></iframe>',
    replace_links=False,
    replace_cosmetic=False
)

_bbcode_parser.add_formatter('size', _render_size)
_bbcode_parser.add_formatter('quote', _render_quote)
