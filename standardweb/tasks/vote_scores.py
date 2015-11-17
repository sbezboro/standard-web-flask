from sqlalchemy import func
from sqlalchemy.orm import joinedload

from standardweb import celery, db
from standardweb.models import ForumPostVote, PlayerStats, Server


MAX_USER_ACTIVE_MULTIPLIER_TIME = 48000  # time in minutes before a player gets 1.0x multiplier
MAX_VOTE_WEIGHT_TIME = 4320  # time in minutes before a vote no longer affects post score


def calculate_user_score_weight(user):
    """Return a weight between 0.0 and 1.0 for use in post score calculation."""
    weight = 1.0

    user_score = float(user.score)

    if user_score < 0:
        weight = 1 / (-user_score + 1)

    if user.player_id:
        total_time = db.session.query(
            func.sum(PlayerStats.time_spent)
        ).join(Server).filter(
            PlayerStats.player_id == user.player_id,
            Server.type == 'survival'
        ).scalar()

        multiplier = min(1.0, float(total_time) / MAX_USER_ACTIVE_MULTIPLIER_TIME)

        weight *= multiplier

    return weight


def calculate_vote_weight(vote, post):
    """Return a weight between 0.0 and 1.0 for use in vote score calculation."""
    difference = vote.created - post.created
    difference_minutes = difference.total_seconds() / 60

    weight = 1 - min(1.0, difference_minutes / MAX_VOTE_WEIGHT_TIME)

    same_ip_votes = ForumPostVote.query.filter(
        ForumPostVote.user_id != vote.user_id,
        ForumPostVote.post_id == post.id,
        ForumPostVote.user_ip == vote.user_ip
    ).count()

    if same_ip_votes:
        weight *= (1 / (50.0 * same_ip_votes))

    return weight


def compute_vote_score(vote, old_vote=None, commit=True):
    """Compute actual score for a vote based on some factors, and update relevant models."""
    post = vote.post
    user = vote.user

    post_user = post.user

    if vote.computed_weight and old_vote:
        # if an existing vote is being updated, just use the already computed weight
        actual_vote = float(vote.vote) - float(old_vote)

        weighted_score = float(vote.computed_weight) * actual_vote
    else:
        user_weight = calculate_user_score_weight(user)
        vote_weight = calculate_vote_weight(vote, post)

        computed_weight = user_weight * vote_weight
        vote.computed_weight = computed_weight
        vote.save(commit=False)

        weighted_score = computed_weight * float(vote.vote)

    post.score = float(post.score) + weighted_score
    post_user.score = float(post_user.score) + weighted_score

    post_user.save(commit=False)
    post.save(commit=commit)


@celery.task()
def compute_vote_score_task(user_id, post_id, old_vote):
    vote = ForumPostVote.query.options(
        joinedload(ForumPostVote.post)
    ).options(
        joinedload(ForumPostVote.user)
    ).filter_by(
        user_id=user_id,
        post_id=post_id
    ).first()

    compute_vote_score(vote, old_vote=old_vote, commit=True)


def compute_scores():
    votes = ForumPostVote.query.options(
        joinedload(ForumPostVote.post)
    ).options(
        joinedload(ForumPostVote.user)
    ).filter(
        ForumPostVote.computed_weight == None
    ).order_by(
        ForumPostVote.created
    )

    for i, vote in enumerate(votes):
        compute_vote_score(vote, commit=False)

        if i and i % 100 == 0:
            db.session.commit()

    db.session.commit()
