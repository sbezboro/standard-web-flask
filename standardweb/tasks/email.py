import requests
import rollbar
from sqlalchemy.orm import joinedload

from standardweb import app
from standardweb import celery
from standardweb.models import User, ForumPost, ForumTopicSubscription


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
