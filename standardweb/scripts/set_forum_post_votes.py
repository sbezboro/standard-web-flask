from standardweb import app, db
from standardweb.models import ForumPost, ForumPostVote


def main():
    posts = ForumPost.query.with_entities(ForumPost.id, ForumPost.user_id)

    for i, post in enumerate(posts):
        vote = ForumPostVote(
            post_id=post.id,
            user_id=post.user_id,
            vote=1
        )
        vote.save(commit=False)

        if i and i % 10000 == 0:
            print 'Inserted', i
            db.session.commit()

    print 'Done!'


if __name__ == '__main__':
    with app.test_request_context():
        app.config.from_object('settings')

        main()
