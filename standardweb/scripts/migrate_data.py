from standardweb.models import *


def migrate_post_topic_counts():
    for category in ForumCategory.query.all():
        for forum in category.forums:
            post_count = 0

            forum.topic_count = ForumTopic.query.filter_by(deleted=False, forum=forum).count()

            for topic in forum.topics:
                topic.post_count = ForumPost.query.filter_by(deleted=False, topic=topic).count()
                topic.save(commit=False)

                post_count += topic.post_count

                for post in topic.posts:
                    post.body = post.body.replace('[size ', '[size=')
                    post.save(commit=False)

            forum.post_count = post_count
            forum.save(commit=False)

    db.session.commit()

    print 'Done post and topic counts'


def main():
    try:
        migrate_post_topic_counts()
    except:
        db.session.rollback()
        raise
    else:
        db.session.commit()

    print 'Done!'


if __name__ == '__main__':
    with app.test_request_context():
        app.config.from_object('settings')

        main()
