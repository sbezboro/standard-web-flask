from flask import json, url_for

import requests
import rollbar

from sqlalchemy.orm import joinedload

from standardweb import app
from standardweb import celery
from standardweb.models import Player, PlayerStats, Server, User, ForumPost, ForumTopicSubscription


@celery.task()
def minute_query():
    # testing
    rollbar.report_message('Query', level='debug')


@celery.task()
def send_email(from_email, to_email, subject, text_body, html_body):
    from standardweb.lib.email import EMAIL_URL

    auth = ('api', app.config['MAILGUN_API_KEY'])

    data = {
        'from': from_email,
        'to': to_email,
        'subject': subject,
        'text': text_body,
        'html': html_body
    }

    result = None

    try:
        result = requests.post(EMAIL_URL, auth=auth, data=data)
    except Exception:
        rollbar.report_exc_info()
    else:
        if result.status_code == 200:
            rollbar.report_message('Email sent', level='info', extra_data={
                'data': data,
                'result': result.json()
            })
        else:
            rollbar.report_message('Problem sending email', level='error', extra_data={
                'data': data,
                'result': result
            })

    return result


@celery.task()
def send_rts_data(user_id, channel, action, payload):
    url = '%s%s/%s' % (app.config['RTS_BASE_URL'], app.config['RTS_PREFIX'], channel)

    headers = {
        'X-Standard-Secret': app.config['RTS_SECRET'],
        'Content-Type': 'application/json'
    }

    data = {
        'user_id': user_id,
        'action': action,
        'payload': payload
    }

    result = None

    try:
        result = requests.post(url, data=json.dumps(data), headers=headers)
    except Exception:
        rollbar.report_exc_info()

    return result


@celery.task()
def api_forum_post(username, uuid, forum_name, topic_name, path, is_new_topic):
    from standardweb.lib.api import api_call

    base_url = url_for('index', _external=True).rstrip('/')

    for server in Server.query.filter_by(online=True):
        data = {
            'forum_name': forum_name,
            'topic_name': topic_name,
            'path': '%s%s' % (base_url, path),
            'is_new_topic': is_new_topic,
            'username': username
        }

        if uuid:
            data['uuid'] = uuid

        api_call(server, 'forum_post', data=data)


@celery.task()
def api_new_message(to_player_id, from_user_id):
    from standardweb.lib.api import api_call

    to_player = Player.query.get(to_player_id)
    from_user = User.query.get(from_user_id)

    from_username = from_user.get_username()
    from_uuid = from_user.player.uuid if from_user.player else None

    url = url_for('messages', username=from_username, _external=True)

    player_stats = PlayerStats.query.options(
        joinedload(PlayerStats.server)
    ).filter(
        PlayerStats.player == to_player,
        Server.online == True
    )

    # send the message only if the player is currently on the server
    servers = [player_stat.server for player_stat in player_stats if player_stat.is_online]

    for server in servers:
        data = {
            'from_username': from_username,
            'from_uuid': from_uuid,
            'to_uuid': to_player.uuid,
            'no_user': not to_player.user,
            'url': url
        }

        api_call(server, 'new_message', data=data)


@celery.task()
def email_news_post_all(forum_post_id):
    from standardweb.lib.email import send_news_post_email

    users = User.query.filter(
        User.email != None
    )

    post = ForumPost.query.get(forum_post_id)
    topic = post.topic

    for user in users:
        send_news_post_email(user, post.body, post.body_html, topic.id, topic.name)


@celery.task()
def email_subscribed_topic_post(forum_post_id):
    from standardweb.lib.email import send_subscribed_topic_post_email

    post = ForumPost.query.get(forum_post_id)
    topic = post.topic

    subscriptions = ForumTopicSubscription.query.options(
        joinedload(ForumTopicSubscription.user)
    ).filter(
        ForumTopicSubscription.topic == topic,
        ForumTopicSubscription.user_id != post.user_id
    ).all()

    for subscription in subscriptions:
        send_subscribed_topic_post_email(subscription.user, post.id, post.body, post.body_html, topic.id, topic.name)
