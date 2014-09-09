from flask import abort
from flask import flash
from flask import g
from flask import redirect
from flask import request
from flask import render_template
from flask import send_file

from standardweb.forms import MoveTopicForm, PostForm, NewTopicForm, ForumSearchForm
from standardweb.lib import api
from standardweb.models import *
from standardweb.views import redirect_old_url

from sqlalchemy import or_
from sqlalchemy.sql.expression import func
from sqlalchemy.orm import joinedload

from datetime import datetime

TOPICS_PER_PAGE = 40
POSTS_PER_PAGE = 20

import rollbar


@app.route('/forums')
def forums():
    categories = ForumCategory.query.options(
        joinedload(ForumCategory.forums)
        .joinedload(Forum.last_post)
        .joinedload(ForumPost.topic)
        .joinedload(ForumTopic.user)
        .joinedload(User.player)
    ).options(
        joinedload(ForumCategory.forums)
        .joinedload(Forum.last_post)
        .joinedload(ForumPost.user)
        .joinedload(User.player)
    ).order_by(ForumCategory.position).all()

    active_forum_ids = set()

    if g.user:
        user = g.user

        if not user.posttracking:
            user.posttracking = ForumPostTracking(user=user)
            user.posttracking.save(commit=True)

        read_topics = user.posttracking.get_topics()
        last_read = user.posttracking.last_read

        if read_topics:
            topics = ForumTopic.query.filter(ForumTopic.id.in_(read_topics.keys()))
            for topic in topics:
                if not last_read or topic.updated > last_read:
                    if topic.last_post_id > read_topics.get(str(topic.id)):
                        active_forum_ids.add(topic.forum_id)

    retval = {
        'categories': categories,
        'active_forum_ids': active_forum_ids
    }

    return render_template('forums/index.html', **retval)


@app.route('/forums/search')
def forum_search():
    all_categories = ForumCategory.query.options(
        joinedload(ForumCategory.forums)
    ).order_by(ForumCategory.position).all()

    page_size = POSTS_PER_PAGE

    page = request.args.get('p') or request.args.get('page')

    try:
        page = max(int(page), 1) if page else 1
    except:
        page = 1

    form = ForumSearchForm(request.args)

    choices = [('', 'All forums')]
    for category in all_categories:
        choices.append((category.name, [(str(x.id), x.name) for x in category.forums]))

    form.forum_id.choices = choices

    form.sort_by.choices = [
        ('post_desc', 'Post Date Descending'),
        ('post_asc', 'Post Date Ascending')
    ]

    retval = {
        'form': form
    }

    if ('query' in request.args or 'user_id' in request.args) and form.validate():
        query = form.query.data
        forum_id = form.forum_id.data
        sort_by = form.sort_by.data
        user_id = form.user_id.data

        order = ForumPost.created.desc()

        if sort_by == 'post_asc':
            order = ForumPost.created.asc()
        elif sort_by == 'post_desc':
            order = ForumPost.created.desc()

        # the result here is a list of topic ids associated with posts,
        # but the topic ids can show up duplicated (ie. more than one
        # matching post in the same topic)
        result = ForumPost.query.with_entities(ForumPost.topic_id) \
            .join(ForumPost.topic).filter(ForumPost.deleted == False) \
            .order_by(order)

        if user_id:
            result = result.filter(ForumPost.user_id == user_id)
        else:
            result = result.filter(or_(ForumPost.body.ilike('%%%s%%' % query),
                                       ForumTopic.name.ilike('%%%s%%' % query)))

        if forum_id:
            result = result.filter(ForumTopic.forum_id == forum_id)

        topic_ids = []
        seen = set()

        # remove duplicate topics by ordering the most recent matching
        # post's topic higher
        if sort_by == 'post_asc':
            for topic_id in [x for x in reversed([x for x, in result])]:
                if topic_id not in seen and not seen.add(topic_id):
                    topic_ids.insert(0, topic_id)
        else:
            for topic_id, in result:
                if topic_id not in seen and not seen.add(topic_id):
                    topic_ids.append(topic_id)

        num_topics = len(topic_ids)
        start = (page - 1) * page_size
        topic_ids = topic_ids[start:start + page_size]

        result = ForumTopic.query.options(
            joinedload(ForumTopic.user)
            .joinedload(User.player)
        ).options(
            joinedload(ForumTopic.last_post)
            .joinedload(ForumPost.user)
            .joinedload(User.player)
        ).filter(ForumTopic.id.in_(topic_ids))

        if topic_ids:
            result = result.order_by(func.field(ForumTopic.id, *topic_ids))

        topics = result.all()

        if user_id:
            retval['by_user'] = User.query.options(joinedload(User.player)).get(user_id)
        elif page == 1:
            rollbar.report_message('Forum searched', level='info', request=request, extra_data={
                'query': query,
                'num_topics': num_topics
            })

        retval.update({
            'query': query,
            'topics': topics,
            'num_topics': num_topics,
            'page_size': page_size,
            'page': page
        })

    return render_template('forums/search.html', **retval)


@app.route('/forum/<int:forum_id>')
def forum(forum_id):
    forum = Forum.query.options(
        joinedload(Forum.moderators)
    ).get(forum_id)

    if not forum:
        abort(404)

    page_size = TOPICS_PER_PAGE
    topic_page_size = POSTS_PER_PAGE

    page = request.args.get('p')

    try:
        page = max(int(page), 1) if page else 1
    except:
        page = 1

    if page < 1 or page > forum.topic_count / page_size + 1:
        return redirect(url_for('forum', forum_id=forum_id))

    if forum.locked:
        order = ForumTopic.sticky.desc(), ForumTopic.created.desc()
    else:
        order = ForumTopic.sticky.desc(), ForumTopic.updated.desc()

    topics = ForumTopic.query.options(
        joinedload(ForumTopic.user)
        .joinedload(User.player)
    ).options(
        joinedload(ForumTopic.last_post)
        .joinedload(ForumPost.user)
        .joinedload(User.player)
    ).filter_by(forum_id=forum_id, deleted=False) \
    .order_by(*order) \
    .limit(page_size) \
    .offset((page - 1) * page_size)

    topics = list(topics)

    active_topic_ids = set()

    if g.user:
        user = g.user
        read_topics = user.posttracking.get_topics()
        last_read = user.posttracking.last_read

        if read_topics:
            for topic in topics:
                if topic.last_post_id > read_topics.get(str(topic.id), 0) \
                        and (not last_read or last_read < topic.updated):
                    active_topic_ids.add(topic.id)

    retval = {
        'forum': forum,
        'topics': topics,
        'active_topic_ids': active_topic_ids,
        'topic_page_size': topic_page_size,
        'page_size': page_size,
        'page': page
    }

    return render_template('forums/forum.html', **retval)


@app.route('/forums/topic/<int:topic_id>', methods=['GET', 'POST'])
def forum_topic(topic_id):
    topic = ForumTopic.query.options(
        joinedload(ForumTopic.forum)
        .joinedload(Forum.moderators)
    ).get(topic_id)

    if not topic or topic.deleted:
        abort(404)

    user = g.user

    form = PostForm()

    if form.validate_on_submit():
        if not user:
            flash('You must log in before you can do that', 'warning')
            return redirect(url_for('login', next=request.path))

        if topic.deleted:
            flash('That topic no longer exists', 'warning')
            return redirect(url_for('forum', forum_id=topic.forum_id))

        if topic.closed:
            flash('That topic has been locked', 'warning')
            return redirect(url_for('forum', forum_id=topic.forum_id))

        if user.forum_ban:
            abort(403)

        body = form.body.data
        image = form.image.data

        last_post = topic.last_post
        if last_post.body == body and last_post.user_id == user.id:
            return redirect(last_post.url)

        post = ForumPost(topic_id=topic.id, user=user, body=body, user_ip=request.remote_addr)

        user.forum_profile.post_count += 1
        user.forum_profile.save(commit=False)

        topic.forum.last_post = post
        topic.forum.post_count += 1
        topic.forum.save(commit=False)

        topic.updated = datetime.utcnow()
        topic.last_post = post
        topic.post_count += 1

        post.save(commit=True)

        if image:
            if not ForumAttachment.create_attachment(post.id, image, commit=True):
                flash('There was a problem with the upload', 'error')

        api.forum_post(user, topic.forum.name, topic.name, post.url, is_new_topic=False)

        return redirect(post.url)

    page = request.args.get('p')

    page_size = POSTS_PER_PAGE

    try:
        page = max(int(page), 1) if page else 1
    except:
        page = 1

    if page < 1 or page > topic.post_count / page_size + 1:
        return redirect(url_for('forum_topic', topic_id=topic_id))

    posts = ForumPost.query.options(
        joinedload(ForumPost.user)
        .joinedload(User.player)
    ).options(
        joinedload(ForumPost.user)
        .joinedload(User.forum_profile)
    ).options(
        joinedload(ForumPost.user)
        .joinedload(User.forum_ban)
    ).options(
        joinedload(ForumPost.attachments)
    ).options(
        joinedload(ForumPost.topic)
        .joinedload(ForumTopic.forum)
    ).filter_by(topic_id=topic_id, deleted=False) \
        .order_by(ForumPost.created) \
        .limit(page_size) \
        .offset((page - 1) * page_size)

    player_ids = set([post.user.player_id for post in posts])

    player_stats = PlayerStats.query.filter(PlayerStats.server_id == app.config['MAIN_SERVER_ID'],
                                            PlayerStats.player_id.in_(player_ids))

    player_stats = {
        stats.player: stats
        for stats in player_stats
    }

    if user:
        topic.update_read(user)

    retval = {
        'topic': topic,
        'posts': posts,
        'player_stats': player_stats,
        'page_size': page_size,
        'page': page,
        'form': form
    }

    return render_template('forums/topic.html', **retval)


@app.route('/forums/post/<int:post_id>')
def forum_post(post_id):
    post = ForumPost.query.get(post_id)

    if not post:
        abort(404)

    topic = post.topic
    posts = topic.posts
    index = posts.index(post)

    page = int(index / POSTS_PER_PAGE) + 1

    if page:
        return redirect(url_for('forum_topic', topic_id=post.topic_id, p=page, _anchor=post.id))

    return redirect(url_for('forum_topic', topic_id=post.topic_id, _anchor=post.id))


@app.route('/forum/<int:forum_id>/new_topic', methods=['GET', 'POST'])
def new_topic(forum_id):
    forum = Forum.query.get(forum_id)

    if not forum:
        abort(404)

    if not g.user:
        flash('You must log in before you can do that', 'warning')
        return redirect(url_for('login', next=request.path))

    user = g.user

    if user.forum_ban:
        abort(403)

    if forum.locked and not user.admin:
        abort(403)

    form = NewTopicForm()

    if form.validate_on_submit():
        title = form.title.data
        body = form.body.data
        image = form.image.data

        last_post = forum.last_post
        if last_post.body == body and last_post.user_id == user.id:
            return redirect(last_post.url)

        topic = ForumTopic(forum=forum, user=user, name=title)
        topic.save(commit=True)

        post = ForumPost(topic_id=topic.id, user=user, body=body, user_ip=request.remote_addr)
        post.save(commit=False)

        user.forum_profile.post_count += 1
        user.forum_profile.save(commit=False)

        forum.last_post = post
        forum.post_count += 1
        forum.topic_count += 1
        forum.save(commit=False)

        topic.last_post = post
        topic.post_count += 1
        topic.save(commit=True)

        if image:
            if not ForumAttachment.create_attachment(post.id, image, commit=True):
                flash('There was a problem with the upload', 'error')

        api.forum_post(user, topic.forum.name, topic.name, post.url, is_new_topic=True)

        return redirect(topic.url)

    retval = {
        'forum': forum,
        'form': form
    }

    return render_template('forums/new_topic.html', **retval)


@app.route('/forums/post/<int:post_id>/edit', methods=['GET', 'POST'])
def edit_post(post_id):
    post = ForumPost.query.options(
        joinedload(ForumPost.topic)
        .joinedload(ForumTopic.forum)
        .joinedload(Forum.moderators)
    ).options(
        joinedload(ForumPost.user)
        .joinedload(User.forum_profile)
    ).get(post_id)

    if not post or post.deleted:
        abort(404)

    if not g.user:
        flash('You must log in before you can do that', 'warning')
        return redirect(url_for('login', next=request.path))

    user = g.user

    if user.forum_ban:
        abort(403)

    if user != post.user and not user.admin and user not in post.topic.forum.moderators:
        abort(403)

    form = PostForm(obj=post)

    if form.validate_on_submit():
        body = request.form['body']

        post.body = body

        post.updated = datetime.utcnow()
        post.updated_by = user

        post.save(commit=True)

        return redirect(post.url)

    retval = {
        'post': post,
        'form': form
    }

    return render_template('forums/edit_post.html', **retval)


@app.route('/forums/topic/<int:topic_id>/status')
def forum_topic_status(topic_id):
    topic = ForumTopic.query.options(
        joinedload(ForumTopic.forum)
        .joinedload(Forum.moderators)
    ).get(topic_id)

    if not topic:
        abort(404)

    if not g.user:
        flash('You must log in before you can do that', 'warning')
        return redirect(url_for('login', next=request.path))

    user = g.user

    if not user.admin and user not in topic.forum.moderators:
        abort(403)

    status = request.args.get('status')

    message = None

    if status == 'close':
        message = 'Topic closed'
        topic.closed = True
    elif status == 'open':
        message = 'Topic opened'
        topic.closed = False
    elif status == 'sticky':
        message = 'Topic stickied'
        topic.sticky = True
    elif status == 'unsticky':
        message = 'Topic unstickied'
        topic.sticky = False

    if message:
        topic.save(commit=True)

        flash(message, 'success')

    return redirect(topic.url)


@app.route('/forums/post/<int:post_id>/delete')
def forum_post_delete(post_id):
    post = ForumPost.query.options(
        joinedload(ForumPost.topic)
        .joinedload(ForumTopic.forum)
        .joinedload(Forum.moderators)
    ).options(
        joinedload(ForumPost.user)
        .joinedload(User.forum_profile)
    ).get(post_id)

    if not post:
        abort(404)

    if not g.user:
        flash('You must log in before you can do that', 'warning')
        return redirect(url_for('login', next=request.path))

    user = g.user

    if not user.admin and user not in post.topic.forum.moderators:
        abort(403)

    first_post = ForumPost.query.join(ForumPost.topic) \
        .filter(ForumTopic.id == post.topic_id) \
        .order_by(ForumPost.created).first()

    post.deleted = True
    post.save(commit=True)

    # if its the first post being deleted, this means the topic will be deleted
    # as well, so reduce the post count for every user in the topic
    if post == first_post:
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

        redirect_url = post.topic.url
        message = 'Post deleted'
    else:
        redirect_url = post.topic.forum.url
        message = 'Topic deleted'

    db.session.commit()

    flash(message, 'success')

    return redirect(redirect_url)


@app.route('/forums/topic/<int:topic_id>/move', methods=['GET', 'POST'])
def move_topic(topic_id):
    topic = ForumTopic.query.options(
        joinedload(ForumTopic.forum)
    ).get(topic_id)

    if not topic or topic.deleted:
        abort(404)

    if not g.user:
        flash('You must log in before you can do that', 'warning')
        return redirect(url_for('login', next=request.path))

    user = g.user

    if not user.admin and not user.moderated_forums:
        abort(403)

    all_categories = ForumCategory.query.options(
        joinedload(ForumCategory.forums)
    ).join(ForumCategory.forums) \
        .filter(Forum.id != topic.forum_id, Forum.locked == False) \
        .order_by(ForumCategory.position)

    form = MoveTopicForm()

    choices = []
    for category in all_categories:
        choices.append((category.name, [(str(x.id), x.name) for x in category.forums if x != topic.forum]))

    form.destination.choices = choices

    if form.validate_on_submit():
        to_forum_id = form.destination.data
        to_forum = Forum.query.get(to_forum_id)

        if topic == topic.forum.last_post.topic:
            new_last_post = ForumPost.query.join(ForumPost.topic).join(ForumTopic.forum) \
                .filter(ForumPost.deleted == False, Forum.id == topic.forum_id,
                        ForumTopic.id != topic.id) \
                .order_by(ForumPost.created.desc()).first()
            topic.forum.last_post = new_last_post

        topic.forum.post_count -= topic.post_count
        topic.forum.topic_count -= 1
        topic.forum.save(commit=False)

        if topic.updated > to_forum.last_post.created:
            to_forum.last_post = topic.last_post

        to_forum.topic_count += 1
        to_forum.post_count += topic.post_count
        to_forum.save(commit=False)

        topic.forum = to_forum
        topic.save(commit=True)

        flash('Topic moved', 'success')

        return redirect(to_forum.url)

    retval = {
        'topic': topic,
        'form': form
    }

    return render_template('forums/move_topic.html', **retval)


@app.route('/forums/all_read')
def all_topics_read():
    if not g.user:
        flash('You must log in before you can do that', 'warning')
        return redirect(url_for('login', next=request.path))

    user = g.user

    user.posttracking.last_read = datetime.utcnow()
    user.save(commit=True)

    flash('All topics marked as read', 'success')

    return redirect(request.referrer)


@app.route('/forums/ban')
def forum_ban():
    if not g.user:
        flash('You must log in before you can do that', 'warning')
        return redirect(url_for('login', next=request.path))

    user = g.user

    if not user.admin and not user.moderated_forums:
        abort(403)

    user_id = request.args['user_id']

    ban = ForumBan(user_id=user_id, by_user_id=user.id)
    ban.save(commit=True)

    flash('User banned from forums', 'success')

    return redirect(request.referrer)


@app.route('/attachment/<hash>')
def forum_attachment(hash):
    attachment = ForumAttachment.query.filter_by(hash=hash).first()
    f = file(attachment.file_path, 'rb')

    return send_file(f, mimetype=attachment.content_type)


redirect_old_url('/forum/', 'forums')
redirect_old_url('/forum/<int:forum_id>/', 'forum', lambda forum_id: {'forum_id': forum_id})
redirect_old_url('/forum/topic/<int:topic_id>/', 'forum_topic', lambda topic_id: {'topic_id': topic_id})
redirect_old_url('/forum/topic/<int:topic_id>/post/add/', 'forum_topic', lambda topic_id: {'topic_id': topic_id},
                  append='1')
redirect_old_url('/forum/post/<int:post_id>/', 'forum_post', lambda post_id: {'post_id': post_id})
redirect_old_url('/forum/user/<username>/', 'player', lambda username: {'username': username})
