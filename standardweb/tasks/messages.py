from datetime import datetime


from standardweb import celery, db
from standardweb.models import Message


@celery.task
def send_new_message_email_task(message_id):
    from standardweb.lib import email

    message = Message.query.get(message_id)

    messages_since = Message.query.filter(
        Message.to_user == message.to_user,
        Message.from_user == message.from_user,
        Message.sent_at > message.sent_at
    ).count()

    if not messages_since:
        messages_to_notify = Message.query.filter(
            Message.to_user == message.to_user,
            Message.from_user == message.from_user,
            Message.notified_at == None,
            Message.seen_at == None
        ).all()

        if messages_to_notify:
            if len(messages_to_notify) == 1:
                email.send_new_message_email(message.to_user, messages_to_notify[0])
            else:
                email.send_new_messages_email(message.to_user, messages_to_notify)

            for message in messages_to_notify:
                message.notified_at = datetime.utcnow()
                message.save(commit=False)

            db.session.commit()
