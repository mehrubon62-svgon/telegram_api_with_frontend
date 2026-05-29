"""CRUD-операции для модуля messages.

Содержит логику работы с сообщениями, реакциями, прочтениями,
драфтами, опросами и хэштегами. Не вызывает commit() сам — это
делает router в конце своего обработчика, чтобы все изменения
(включая admin_log и unread-счётчики) применились атомарно.
"""
import re
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from models import (
    Chat,
    ChatMember,
    ChatMemberRole,
    ChatType,
    Message,
    MessageType,
    MessageEditHistory,
    Attachment,
    MessageReaction,
    MessageRead,
    MessageMention,
    MessageView,
    MessageDraft,
    PinnedMessage,
    Hashtag,
    MessageHashtag,
    Poll,
    PollOption,
    PollVote,
    User,
)


def utc() -> datetime:
    return datetime.now(timezone.utc)


# =====================================================================
#  Hashtags / mentions парсинг
# =====================================================================

_HASHTAG_RE = re.compile(r"(?<![\w@])#([\w\u00a0-\uffff]{1,100})", re.UNICODE)
_MENTION_RE = re.compile(r"(?<![\w])@([a-zA-Z][a-zA-Z0-9_]{2,49})")


def extract_hashtags(text: str | None) -> list[str]:
    if not text:
        return []
    seen = set()
    result = []
    for match in _HASHTAG_RE.findall(text):
        tag = match.lower()
        if tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    return result


def extract_mentions(text: str | None) -> list[str]:
    if not text:
        return []
    seen = set()
    result = []
    for match in _MENTION_RE.findall(text):
        u = match.lower()
        if u in seen:
            continue
        seen.add(u)
        result.append(u)
    return result


def attach_hashtags(db: Session, message_id: int, text: str | None) -> None:
    tags = extract_hashtags(text)
    for tag in tags:
        h = db.query(Hashtag).filter(Hashtag.tag == tag).first()
        if not h:
            h = Hashtag(tag=tag, usage_count=0)
            db.add(h)
            db.flush()
        h.usage_count += 1
        db.add(MessageHashtag(message_id=message_id, hashtag_id=h.id))


def attach_mentions(db: Session, chat_id: int, message_id: int, text: str | None) -> list[int]:
    """Создаёт MessageMention для каждого реального @username, кто состоит в чате."""
    usernames = extract_mentions(text)
    if not usernames:
        return []
    rows = (
        db.query(User)
        .filter(func.lower(User.username).in_(usernames))
        .all()
    )
    if not rows:
        return []

    member_user_ids = {
        m.user_id for m in db.query(ChatMember.user_id).filter(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id.in_([u.id for u in rows]),
            ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
        ).all()
    }

    mentioned = []
    for u in rows:
        if u.id in member_user_ids:
            db.add(MessageMention(message_id=message_id, mentioned_user_id=u.id))
            mentioned.append(u.id)
    return mentioned


# =====================================================================
#  Send message
# =====================================================================

def create_message(
    db: Session,
    chat: Chat,
    *,
    sender_id: int | None,
    type: MessageType,
    text: str | None = None,
    entities: list[dict] | None = None,
    reply_to_id: int | None = None,
    reply_quote: dict | None = None,
    topic_id: int | None = None,
    is_silent: bool = False,
    self_destruct_seconds: int | None = None,
    scheduled_at: datetime | None = None,
    original_language: str | None = None,
    reply_markup: dict | None = None,
    forward_from_user_id: int | None = None,
    forward_from_chat_id: int | None = None,
    forward_from_message_id: int | None = None,
    forward_sender_name: str | None = None,
    forward_date: datetime | None = None,
    via_bot_id: int | None = None,
    attachments: list[dict] | None = None,
) -> Message:
    msg = Message(
        chat_id=chat.id,
        topic_id=topic_id,
        sender_id=sender_id,
        type=type,
        text=text,
        entities=entities,
        reply_to_id=reply_to_id,
        is_silent=is_silent,
        self_destruct_seconds=self_destruct_seconds,
        scheduled_at=scheduled_at,
        is_scheduled=scheduled_at is not None,
        original_language=original_language,
        reply_markup=reply_markup,
        forward_from_user_id=forward_from_user_id,
        forward_from_chat_id=forward_from_chat_id,
        forward_from_message_id=forward_from_message_id,
        forward_sender_name=forward_sender_name,
        forward_date=forward_date,
        via_bot_id=via_bot_id,
        is_via_bot=via_bot_id is not None,
    )
    if reply_quote:
        msg.reply_quote_text = reply_quote.get("text")
        msg.reply_quote_offset = reply_quote.get("offset")
        msg.reply_quote_entities = reply_quote.get("entities")

    # Если есть thread_root через reply
    if reply_to_id:
        parent = db.query(Message).filter(Message.id == reply_to_id).first()
        if parent:
            msg.thread_root_id = parent.thread_root_id or parent.id

    db.add(msg)
    db.flush()  # нужно msg.id для атачей и хэштегов

    if attachments:
        for att in attachments:
            db.add(Attachment(message_id=msg.id, **att))

    if not msg.is_scheduled and not msg.forward_from_message_id:
        attach_hashtags(db, msg.id, text)

    mentioned_ids = attach_mentions(db, chat.id, msg.id, text) if not msg.is_scheduled else []

    if not msg.is_scheduled:
        chat.last_message_id = msg.id
        # Топик: обновляем last_message_id
        if topic_id:
            from models import ChatTopic
            topic = db.query(ChatTopic).filter(ChatTopic.id == topic_id).first()
            if topic:
                topic.last_message_id = msg.id

        # Bump unread у всех остальных участников + увеличить mentions
        members = (
            db.query(ChatMember)
            .filter(
                ChatMember.chat_id == chat.id,
                ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
            )
            .all()
        )
        for m in members:
            if m.user_id == sender_id:
                continue
            m.unread_count = (m.unread_count or 0) + 1
            if m.user_id in mentioned_ids:
                m.unread_mentions_count = (m.unread_mentions_count or 0) + 1

    return msg


# =====================================================================
#  Read / fetch
# =====================================================================

def get_message(db: Session, message_id: int) -> Message | None:
    return db.query(Message).filter(Message.id == message_id).first()


def list_messages(
    db: Session,
    chat_id: int,
    *,
    topic_id: int | None = None,
    before_id: int | None = None,
    after_id: int | None = None,
    limit: int = 50,
    include_deleted: bool = False,
) -> list[Message]:
    q = db.query(Message).filter(Message.chat_id == chat_id, Message.is_scheduled.is_(False))
    if topic_id is not None:
        q = q.filter(Message.topic_id == topic_id)
    if not include_deleted:
        q = q.filter(Message.is_deleted.is_(False))

    if after_id is not None:
        # пагинация вперёд от after_id
        items = (
            q.filter(Message.id > after_id)
            .order_by(Message.id.asc())
            .limit(limit)
            .all()
        )
        return items

    if before_id is not None:
        # пагинация назад: тянем последние N до before_id, отдаём в хронологическом порядке
        items = (
            q.filter(Message.id < before_id)
            .order_by(Message.id.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(items))

    # Без курсора — последние N в хронологическом порядке
    items = q.order_by(Message.id.desc()).limit(limit).all()
    return list(reversed(items))


def get_attachments(db: Session, message_ids: list[int]) -> dict[int, list[Attachment]]:
    if not message_ids:
        return {}
    rows = db.query(Attachment).filter(Attachment.message_id.in_(message_ids)).order_by(Attachment.position.asc()).all()
    result: dict[int, list[Attachment]] = {}
    for a in rows:
        result.setdefault(a.message_id, []).append(a)
    return result


# =====================================================================
#  Edit / delete
# =====================================================================

def edit_message(
    db: Session,
    msg: Message,
    *,
    text: str | None = None,
    entities: list[dict] | None = None,
    reply_markup: dict | None = None,
) -> Message:
    db.add(MessageEditHistory(
        message_id=msg.id,
        text=msg.text,
        entities=msg.entities,
    ))
    if text is not None:
        msg.text = text
    if entities is not None:
        msg.entities = entities
    if reply_markup is not None:
        msg.reply_markup = reply_markup
    msg.is_edited = True
    msg.edited_at = utc()
    return msg


def delete_message(db: Session, msg: Message, *, for_everyone: bool = True) -> None:
    msg.is_deleted = True
    if for_everyone:
        msg.text = None
        msg.entities = None
        msg.reply_markup = None
        # Удаляем атачи и связки
        db.query(Attachment).filter(Attachment.message_id == msg.id).delete(synchronize_session=False)
        db.query(MessageHashtag).filter(MessageHashtag.message_id == msg.id).delete(synchronize_session=False)


def get_edit_history(db: Session, message_id: int) -> list[MessageEditHistory]:
    return (
        db.query(MessageEditHistory)
        .filter(MessageEditHistory.message_id == message_id)
        .order_by(MessageEditHistory.edited_at.desc())
        .all()
    )


# =====================================================================
#  Pinned
# =====================================================================

def pin_message(db: Session, chat: Chat, message_id: int, *, by_user_id: int) -> PinnedMessage:
    existing = (
        db.query(PinnedMessage)
        .filter(PinnedMessage.chat_id == chat.id, PinnedMessage.message_id == message_id)
        .first()
    )
    if existing:
        return existing
    pinned = PinnedMessage(chat_id=chat.id, message_id=message_id, pinned_by_id=by_user_id)
    db.add(pinned)
    msg = db.query(Message).filter(Message.id == message_id).first()
    if msg:
        msg.is_pinned = True
    chat.pinned_message_id = message_id
    return pinned


def unpin_message(db: Session, chat: Chat, message_id: int) -> bool:
    record = (
        db.query(PinnedMessage)
        .filter(PinnedMessage.chat_id == chat.id, PinnedMessage.message_id == message_id)
        .first()
    )
    if not record:
        return False
    db.delete(record)
    msg = db.query(Message).filter(Message.id == message_id).first()
    if msg:
        msg.is_pinned = False
    if chat.pinned_message_id == message_id:
        # Откатываем на самое свежее закреплённое
        latest = (
            db.query(PinnedMessage)
            .filter(PinnedMessage.chat_id == chat.id, PinnedMessage.message_id != message_id)
            .order_by(PinnedMessage.pinned_at.desc())
            .first()
        )
        chat.pinned_message_id = latest.message_id if latest else None
    return True


def list_pinned(db: Session, chat_id: int) -> list[Message]:
    return (
        db.query(Message)
        .join(PinnedMessage, PinnedMessage.message_id == Message.id)
        .filter(PinnedMessage.chat_id == chat_id, Message.is_deleted.is_(False))
        .order_by(PinnedMessage.pinned_at.desc())
        .all()
    )


# =====================================================================
#  Reactions
# =====================================================================

def toggle_reaction(
    db: Session,
    message_id: int,
    user_id: int,
    emoji: str,
    *,
    is_big: bool = False,
) -> tuple[bool, list[MessageReaction]]:
    existing = (
        db.query(MessageReaction)
        .filter(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == user_id,
            MessageReaction.emoji == emoji,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        added = False
    else:
        db.add(MessageReaction(message_id=message_id, user_id=user_id, emoji=emoji, is_big=is_big))
        added = True

    db.flush()
    reactions = (
        db.query(MessageReaction)
        .filter(MessageReaction.message_id == message_id)
        .all()
    )
    return added, reactions


def get_reactions(db: Session, message_id: int) -> list[MessageReaction]:
    return db.query(MessageReaction).filter(MessageReaction.message_id == message_id).all()


# =====================================================================
#  Read receipts
# =====================================================================

def mark_chat_read(
    db: Session,
    chat_id: int,
    user_id: int,
    *,
    up_to_message_id: int,
) -> list[int]:
    """Отмечает прочитанным до up_to_message_id (включительно). Возвращает id новых прочитанных."""
    member = (
        db.query(ChatMember)
        .filter(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
        .first()
    )
    if not member:
        return []

    last_read = member.last_read_message_id or 0
    if up_to_message_id <= last_read:
        return []

    new_msgs = (
        db.query(Message)
        .filter(
            Message.chat_id == chat_id,
            Message.id > last_read,
            Message.id <= up_to_message_id,
            Message.is_deleted.is_(False),
            Message.is_scheduled.is_(False),
        )
        .order_by(Message.id.asc())
        .all()
    )

    new_ids: list[int] = []
    for m in new_msgs:
        if m.sender_id == user_id:
            continue
        # idempotent insert
        exists = (
            db.query(MessageRead)
            .filter(MessageRead.message_id == m.id, MessageRead.user_id == user_id)
            .first()
        )
        if not exists:
            db.add(MessageRead(message_id=m.id, user_id=user_id))
        new_ids.append(m.id)

    member.last_read_message_id = up_to_message_id

    # Сбрасываем unread-счётчики
    incoming_remaining = (
        db.query(func.count(Message.id))
        .filter(
            Message.chat_id == chat_id,
            Message.id > up_to_message_id,
            Message.sender_id != user_id,
            Message.is_deleted.is_(False),
            Message.is_scheduled.is_(False),
        )
        .scalar()
    )
    member.unread_count = int(incoming_remaining or 0)

    # Прочитанные ментионы — больше не unread
    db.query(MessageMention).filter(
        MessageMention.mentioned_user_id == user_id,
        MessageMention.message_id.in_([m.id for m in new_msgs]) if new_msgs else False,
    ).update({"is_read": True}, synchronize_session=False)

    mentions_remaining = (
        db.query(func.count(MessageMention.id))
        .join(Message, Message.id == MessageMention.message_id)
        .filter(
            Message.chat_id == chat_id,
            MessageMention.mentioned_user_id == user_id,
            MessageMention.is_read.is_(False),
            Message.is_deleted.is_(False),
        )
        .scalar()
    )
    member.unread_mentions_count = int(mentions_remaining or 0)

    return new_ids


def list_message_reads(db: Session, message_id: int) -> list[MessageRead]:
    return db.query(MessageRead).filter(MessageRead.message_id == message_id).all()


def increment_views(db: Session, message_id: int, user_id: int) -> None:
    exists = (
        db.query(MessageView)
        .filter(MessageView.message_id == message_id, MessageView.user_id == user_id)
        .first()
    )
    if exists:
        return
    db.add(MessageView(message_id=message_id, user_id=user_id))
    msg = db.query(Message).filter(Message.id == message_id).first()
    if msg:
        msg.views_count = (msg.views_count or 0) + 1


# =====================================================================
#  Mentions
# =====================================================================

def list_unread_mentions(db: Session, chat_id: int, user_id: int) -> list[Message]:
    return (
        db.query(Message)
        .join(MessageMention, MessageMention.message_id == Message.id)
        .filter(
            Message.chat_id == chat_id,
            MessageMention.mentioned_user_id == user_id,
            MessageMention.is_read.is_(False),
            Message.is_deleted.is_(False),
        )
        .order_by(Message.id.asc())
        .all()
    )


def mark_mentions_read(db: Session, chat_id: int, user_id: int) -> int:
    count = (
        db.query(MessageMention)
        .filter(
            MessageMention.mentioned_user_id == user_id,
            MessageMention.is_read.is_(False),
            MessageMention.message_id.in_(
                db.query(Message.id).filter(Message.chat_id == chat_id)
            ),
        )
        .update({"is_read": True}, synchronize_session=False)
    )
    member = (
        db.query(ChatMember)
        .filter(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
        .first()
    )
    if member:
        member.unread_mentions_count = 0
    return count


# =====================================================================
#  Drafts
# =====================================================================

def get_draft(db: Session, user_id: int, chat_id: int, topic_id: int | None = None) -> MessageDraft | None:
    q = db.query(MessageDraft).filter(MessageDraft.user_id == user_id, MessageDraft.chat_id == chat_id)
    if topic_id is None:
        q = q.filter(MessageDraft.topic_id.is_(None))
    else:
        q = q.filter(MessageDraft.topic_id == topic_id)
    return q.first()


def upsert_draft(
    db: Session,
    user_id: int,
    chat_id: int,
    *,
    text: str | None,
    reply_to_id: int | None,
    topic_id: int | None,
) -> MessageDraft:
    draft = get_draft(db, user_id, chat_id, topic_id)
    if not draft:
        draft = MessageDraft(user_id=user_id, chat_id=chat_id, topic_id=topic_id)
        db.add(draft)
    draft.text = text
    draft.reply_to_id = reply_to_id
    draft.updated_at = utc()
    return draft


def delete_draft(db: Session, user_id: int, chat_id: int, topic_id: int | None = None) -> bool:
    draft = get_draft(db, user_id, chat_id, topic_id)
    if not draft:
        return False
    db.delete(draft)
    return True


# =====================================================================
#  Search
# =====================================================================

def search_in_chat(
    db: Session,
    chat_id: int,
    query: str,
    *,
    limit: int = 50,
    before_id: int | None = None,
) -> list[Message]:
    pat = f"%{query}%"
    q = (
        db.query(Message)
        .filter(
            Message.chat_id == chat_id,
            Message.is_deleted.is_(False),
            Message.is_scheduled.is_(False),
            Message.text.ilike(pat),
        )
    )
    if before_id is not None:
        q = q.filter(Message.id < before_id)
    return q.order_by(Message.id.desc()).limit(limit).all()


def search_global(
    db: Session,
    user_id: int,
    query: str,
    *,
    limit: int = 50,
) -> list[Message]:
    """Поиск в чатах, где пользователь активный участник."""
    pat = f"%{query}%"
    chat_ids_q = (
        db.query(ChatMember.chat_id)
        .filter(
            ChatMember.user_id == user_id,
            ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
        )
    )
    return (
        db.query(Message)
        .filter(
            Message.chat_id.in_(chat_ids_q),
            Message.is_deleted.is_(False),
            Message.is_scheduled.is_(False),
            Message.text.ilike(pat),
        )
        .order_by(Message.id.desc())
        .limit(limit)
        .all()
    )


def list_by_hashtag(db: Session, tag: str, *, limit: int = 50) -> list[Message]:
    h = db.query(Hashtag).filter(Hashtag.tag == tag.lower().lstrip("#")).first()
    if not h:
        return []
    return (
        db.query(Message)
        .join(MessageHashtag, MessageHashtag.message_id == Message.id)
        .filter(MessageHashtag.hashtag_id == h.id, Message.is_deleted.is_(False))
        .order_by(Message.id.desc())
        .limit(limit)
        .all()
    )


# =====================================================================
#  Polls
# =====================================================================

def create_poll(
    db: Session,
    *,
    message_id: int,
    question: str,
    options: list[str],
    is_anonymous: bool,
    allows_multiple_answers: bool,
    is_quiz: bool,
    correct_option_index: int | None,
    explanation: str | None,
    close_at: datetime | None,
) -> Poll:
    poll = Poll(
        message_id=message_id,
        question=question,
        is_anonymous=is_anonymous,
        allows_multiple_answers=allows_multiple_answers,
        is_quiz=is_quiz,
        explanation=explanation,
        close_at=close_at,
    )
    db.add(poll)
    db.flush()

    option_records = []
    for idx, text in enumerate(options):
        opt = PollOption(poll_id=poll.id, text=text, position=idx)
        db.add(opt)
        option_records.append(opt)
    db.flush()

    if is_quiz and correct_option_index is not None and 0 <= correct_option_index < len(option_records):
        poll.correct_option_id = option_records[correct_option_index].id

    return poll


def get_poll(db: Session, poll_id: int) -> Poll | None:
    return db.query(Poll).filter(Poll.id == poll_id).first()


def get_poll_by_message(db: Session, message_id: int) -> Poll | None:
    return db.query(Poll).filter(Poll.message_id == message_id).first()


def list_poll_options(db: Session, poll_id: int) -> list[PollOption]:
    return db.query(PollOption).filter(PollOption.poll_id == poll_id).order_by(PollOption.position.asc()).all()


def vote_poll(
    db: Session,
    poll: Poll,
    user_id: int,
    option_ids: list[int],
) -> Poll:
    if poll.is_closed:
        raise ValueError("poll_closed")

    existing_votes = (
        db.query(PollVote).filter(PollVote.poll_id == poll.id, PollVote.user_id == user_id).all()
    )
    options = list_poll_options(db, poll.id)
    valid_ids = {o.id for o in options}
    if not all(oid in valid_ids for oid in option_ids):
        raise ValueError("invalid_option")

    if not poll.allows_multiple_answers and len(option_ids) > 1:
        raise ValueError("multiple_not_allowed")

    # Сбрасываем старые
    for v in existing_votes:
        opt = next((o for o in options if o.id == v.option_id), None)
        if opt:
            opt.voter_count = max((opt.voter_count or 1) - 1, 0)
        db.delete(v)
    if existing_votes:
        poll.total_voters = max((poll.total_voters or 1) - 1, 0)

    # Записываем новые
    if option_ids:
        for oid in option_ids:
            db.add(PollVote(poll_id=poll.id, option_id=oid, user_id=user_id))
            opt = next((o for o in options if o.id == oid), None)
            if opt:
                opt.voter_count = (opt.voter_count or 0) + 1
        poll.total_voters = (poll.total_voters or 0) + 1

    return poll


def get_user_votes(db: Session, poll_id: int, user_id: int) -> list[int]:
    rows = (
        db.query(PollVote.option_id)
        .filter(PollVote.poll_id == poll_id, PollVote.user_id == user_id)
        .all()
    )
    return [r[0] for r in rows]


def close_poll(db: Session, poll: Poll) -> Poll:
    poll.is_closed = True
    return poll
