"""CRUD сторис."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import (
    Story,
    StoryView,
    StoryReaction,
    StoryPrivacyType,
    CloseFriend,
    Contact,
    User,
)


STORY_TTL_HOURS = 24


def utc() -> datetime:
    return datetime.now(timezone.utc)


# =====================================================================
#  Create / lifecycle
# =====================================================================

def create_story(
    db: Session,
    *,
    author_id: int,
    media_url: str,
    media_type: str,
    thumbnail_url: str | None = None,
    duration: int | None = None,
    width: int | None = None,
    height: int | None = None,
    caption: str | None = None,
    entities: list[dict] | None = None,
    privacy: StoryPrivacyType = StoryPrivacyType.everybody,
    allowed_user_ids: list[int] | None = None,
    excluded_user_ids: list[int] | None = None,
    pinned: bool = False,
    allow_replies: bool = True,
    allow_reactions: bool = True,
    allow_forwards: bool = True,
    chat_id: int | None = None,
) -> Story:
    story = Story(
        author_id=author_id,
        chat_id=chat_id,
        media_url=media_url,
        thumbnail_url=thumbnail_url,
        media_type=media_type,
        duration=duration,
        width=width,
        height=height,
        caption=caption,
        entities=entities,
        privacy=privacy,
        allowed_user_ids=allowed_user_ids,
        excluded_user_ids=excluded_user_ids,
        pinned=pinned,
        allow_replies=allow_replies,
        allow_reactions=allow_reactions,
        allow_forwards=allow_forwards,
        expires_at=utc() + timedelta(hours=STORY_TTL_HOURS),
    )
    db.add(story)
    return story


def get_story(db: Session, story_id: int) -> Story | None:
    return db.query(Story).filter(Story.id == story_id).first()


def delete_story(db: Session, story: Story) -> None:
    db.delete(story)


def list_pinned_for_user(db: Session, user_id: int) -> list[Story]:
    """Закреплённые в профиле сторис (не истекшие учитываются как живые,
    истекшие — только если pinned=True, как в TG)."""
    return (
        db.query(Story)
        .filter(Story.author_id == user_id, Story.pinned.is_(True))
        .order_by(Story.created_at.desc())
        .all()
    )


def list_active_for_user(db: Session, user_id: int) -> list[Story]:
    """Активные (не истекли) сторис конкретного автора."""
    return (
        db.query(Story)
        .filter(Story.author_id == user_id, Story.expires_at > utc())
        .order_by(Story.created_at.asc())
        .all()
    )


# =====================================================================
#  Privacy / visibility
# =====================================================================

def is_close_friend(db: Session, owner_id: int, user_id: int) -> bool:
    return (
        db.query(CloseFriend)
        .filter(CloseFriend.owner_id == owner_id, CloseFriend.friend_id == user_id)
        .first()
        is not None
    )


def is_contact(db: Session, owner_id: int, user_id: int) -> bool:
    return (
        db.query(Contact)
        .filter(Contact.owner_id == owner_id, Contact.contact_id == user_id)
        .first()
        is not None
    )


def can_view_story(db: Session, story: Story, viewer_id: int) -> bool:
    if story.author_id == viewer_id:
        return True
    if story.excluded_user_ids and viewer_id in story.excluded_user_ids:
        return False

    if story.privacy == StoryPrivacyType.everybody:
        return True
    if story.privacy == StoryPrivacyType.contacts:
        return is_contact(db, story.author_id, viewer_id)
    if story.privacy == StoryPrivacyType.close_friends:
        return is_close_friend(db, story.author_id, viewer_id)
    if story.privacy == StoryPrivacyType.selected:
        return bool(story.allowed_user_ids) and viewer_id in story.allowed_user_ids
    return False


# =====================================================================
#  Feed
# =====================================================================

def feed_authors_for_user(db: Session, user_id: int) -> list[int]:
    """
    Авторы для ленты сторис: контакты + близкие друзья + сам пользователь.
    Тех, у кого нет активных сторис, отфильтруем дальше при сборке ленты.
    """
    contact_ids = [
        r[0] for r in
        db.query(Contact.contact_id).filter(Contact.owner_id == user_id).all()
    ]
    cf_ids = [
        r[0] for r in
        db.query(CloseFriend.friend_id).filter(CloseFriend.owner_id == user_id).all()
    ]
    return list({user_id, *contact_ids, *cf_ids})


def list_active_stories_by_authors(
    db: Session,
    author_ids: list[int],
    *,
    viewer_id: int,
) -> list[Story]:
    if not author_ids:
        return []
    items = (
        db.query(Story)
        .filter(
            Story.author_id.in_(author_ids),
            Story.expires_at > utc(),
        )
        .order_by(Story.author_id.asc(), Story.created_at.asc())
        .all()
    )
    return [s for s in items if can_view_story(db, s, viewer_id)]


# =====================================================================
#  Views
# =====================================================================

def record_view(db: Session, story: Story, viewer_id: int) -> bool:
    """Возвращает True, если просмотр был зарегистрирован впервые."""
    existing = (
        db.query(StoryView)
        .filter(StoryView.story_id == story.id, StoryView.user_id == viewer_id)
        .first()
    )
    if existing:
        return False
    db.add(StoryView(story_id=story.id, user_id=viewer_id))
    story.views_count = (story.views_count or 0) + 1
    return True


def has_viewed(db: Session, story_id: int, viewer_id: int) -> bool:
    return (
        db.query(StoryView)
        .filter(StoryView.story_id == story_id, StoryView.user_id == viewer_id)
        .first()
        is not None
    )


def list_viewers(db: Session, story_id: int) -> list[tuple[StoryView, User]]:
    return (
        db.query(StoryView, User)
        .join(User, User.id == StoryView.user_id)
        .filter(StoryView.story_id == story_id)
        .order_by(StoryView.viewed_at.desc())
        .all()
    )


# =====================================================================
#  Reactions
# =====================================================================

def get_my_reaction(db: Session, story_id: int, user_id: int) -> StoryReaction | None:
    return (
        db.query(StoryReaction)
        .filter(StoryReaction.story_id == story_id, StoryReaction.user_id == user_id)
        .first()
    )


def set_reaction(
    db: Session,
    story: Story,
    user_id: int,
    emoji: str,
) -> StoryReaction:
    existing = get_my_reaction(db, story.id, user_id)
    if existing:
        existing.emoji = emoji
        return existing
    reaction = StoryReaction(story_id=story.id, user_id=user_id, emoji=emoji)
    db.add(reaction)
    story.reactions_count = (story.reactions_count or 0) + 1
    return reaction


def remove_reaction(db: Session, story: Story, user_id: int) -> bool:
    existing = get_my_reaction(db, story.id, user_id)
    if not existing:
        return False
    db.delete(existing)
    story.reactions_count = max((story.reactions_count or 1) - 1, 0)
    return True


# =====================================================================
#  Close friends
# =====================================================================

def list_close_friends(db: Session, user_id: int) -> list[int]:
    rows = db.query(CloseFriend.friend_id).filter(CloseFriend.owner_id == user_id).all()
    return [r[0] for r in rows]


def set_close_friends(db: Session, user_id: int, friend_ids: list[int]) -> list[int]:
    """Замещает список близких друзей."""
    db.query(CloseFriend).filter(CloseFriend.owner_id == user_id).delete(synchronize_session=False)
    unique = {fid for fid in friend_ids if fid != user_id}
    for fid in unique:
        db.add(CloseFriend(owner_id=user_id, friend_id=fid))
    return list(unique)
