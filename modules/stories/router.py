"""HTTP API сторис.

  • POST   /stories                — создать
  • GET    /stories/feed           — лента (по авторам с активными сторис)
  • GET    /users/{id}/stories     — все активные сторис автора (с учётом privacy)
  • GET    /users/{id}/stories/pinned — закреплённые в профиле
  • GET    /stories/{id}           — одна сторис, авто-регистрация просмотра
  • DELETE /stories/{id}           — удалить (только автор)
  • PUT    /stories/{id}/pin       — закрепить/открепить в профиле
  • POST   /stories/{id}/view      — отметить просмотренной (явно, на случай если
                                     клиент уже хранит её в кэше)
  • POST   /stories/{id}/reaction  — поставить/изменить реакцию
  • DELETE /stories/{id}/reaction  — снять
  • POST   /stories/{id}/reply     — ответить на сторис (создаёт обычное private
                                     сообщение типа story_reply автору)
  • GET    /stories/{id}/viewers   — список зрителей (только автор)
  • GET    /stories/close-friends  / PUT — управлять списком «близких друзей»
"""
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models import (
    get_db,
    User,
    Story,
    StoryPrivacyType,
    Chat,
    ChatType,
    ChatMember,
    ChatMemberRole,
    Message,
    MessageType,
    StoryReaction,
)
from dependencies import get_current_user
from modules.users.crud import get_user_by_id
from modules.chats import crud as chats_crud
from modules.messages import crud as messages_crud
from modules.notifications import crud as notif_crud
from modules.websockets.events import (
    EVT_NEW_MESSAGE,
    broadcast_to_chat_sync,
    send_to_user_sync,
    EVT_NOTIFICATION,
)

from modules.stories import crud
from modules.stories.schemas import (
    StoryCreate,
    StoryOut,
    StoryAuthor,
    StoryFeedItem,
    StoryReactionIn,
    StoryReplyIn,
    StoryViewerOut,
    CloseFriendsUpdate,
    CloseFriendsOut,
)


router = APIRouter(prefix="/stories", tags=["Stories"])
user_stories_router = APIRouter(prefix="/users", tags=["Stories"])


# =====================================================================
#  Serialization
# =====================================================================

def _serialize_story(db: Session, story: Story, user: User, *, author: User | None = None) -> StoryOut:
    if author is None:
        author = get_user_by_id(db, story.author_id)
    is_viewed = crud.has_viewed(db, story.id, user.id) if user.id != story.author_id else True
    my_reaction = crud.get_my_reaction(db, story.id, user.id)
    return StoryOut(
        id=story.id,
        author=StoryAuthor.model_validate(author),
        chat_id=story.chat_id,
        media_url=story.media_url,
        thumbnail_url=story.thumbnail_url,
        media_type=story.media_type,
        duration=story.duration,
        width=story.width,
        height=story.height,
        caption=story.caption,
        entities=story.entities,
        privacy=story.privacy,
        pinned=story.pinned,
        allow_replies=story.allow_replies,
        allow_reactions=story.allow_reactions,
        allow_forwards=story.allow_forwards,
        views_count=story.views_count or 0,
        reactions_count=story.reactions_count or 0,
        is_viewed=is_viewed,
        my_reaction=my_reaction.emoji if my_reaction else None,
        expires_at=story.expires_at,
        created_at=story.created_at,
    )


# =====================================================================
#  Create / delete
# =====================================================================

@router.post("", response_model=StoryOut, status_code=201)
def create_story_endpoint(
    data: StoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = crud.create_story(
        db,
        author_id=user.id,
        media_url=data.media_url,
        media_type=data.media_type,
        thumbnail_url=data.thumbnail_url,
        duration=data.duration,
        width=data.width,
        height=data.height,
        caption=data.caption,
        entities=data.entities,
        privacy=data.privacy,
        allowed_user_ids=data.allowed_user_ids,
        excluded_user_ids=data.excluded_user_ids,
        pinned=data.pinned,
        allow_replies=data.allow_replies,
        allow_reactions=data.allow_reactions,
        allow_forwards=data.allow_forwards,
        chat_id=data.chat_id,
    )
    db.commit()
    db.refresh(story)
    return _serialize_story(db, story, user, author=user)


@router.delete("/{story_id}")
def delete_story_endpoint(
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = crud.get_story(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if story.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only author can delete")
    crud.delete_story(db, story)
    db.commit()
    return {"detail": "Deleted"}


@router.put("/{story_id}/pin", response_model=StoryOut)
def toggle_pin_story(
    story_id: int,
    pinned: bool = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = crud.get_story(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if story.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only author can pin")
    story.pinned = pinned
    db.commit()
    db.refresh(story)
    return _serialize_story(db, story, user, author=user)


# =====================================================================
#  Feed / lists
# =====================================================================

@router.get("/feed", response_model=list[StoryFeedItem])
def feed(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    author_ids = crud.feed_authors_for_user(db, user.id)
    stories = crud.list_active_stories_by_authors(db, author_ids, viewer_id=user.id)

    by_author: dict[int, list[Story]] = defaultdict(list)
    for s in stories:
        by_author[s.author_id].append(s)
    if not by_author:
        return []

    authors = {u.id: u for u in db.query(User).filter(User.id.in_(by_author.keys())).all()}

    feed_items: list[StoryFeedItem] = []
    for aid, items in by_author.items():
        author = authors.get(aid)
        if not author:
            continue
        serialized = [_serialize_story(db, s, user, author=author) for s in items]
        has_unviewed = any(not s.is_viewed for s in serialized)
        feed_items.append(StoryFeedItem(
            author=StoryAuthor.model_validate(author),
            has_unviewed=has_unviewed,
            stories=serialized,
        ))
    # Сначала свои, потом непросмотренные, потом остальные
    feed_items.sort(key=lambda x: (x.author.id != user.id, not x.has_unviewed))
    return feed_items


@user_stories_router.get("/{user_id}/stories", response_model=list[StoryOut])
def user_active_stories(
    user_id: int,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    author = get_user_by_id(db, user_id)
    if not author or not author.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    items = crud.list_active_for_user(db, user_id)
    items = [s for s in items if crud.can_view_story(db, s, viewer.id)]
    return [_serialize_story(db, s, viewer, author=author) for s in items]


@user_stories_router.get("/{user_id}/stories/pinned", response_model=list[StoryOut])
def user_pinned_stories(
    user_id: int,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    author = get_user_by_id(db, user_id)
    if not author or not author.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    items = crud.list_pinned_for_user(db, user_id)
    items = [s for s in items if crud.can_view_story(db, s, viewer.id)]
    return [_serialize_story(db, s, viewer, author=author) for s in items]


# =====================================================================
#  Single story / view
# =====================================================================

@router.get("/{story_id}", response_model=StoryOut)
def get_story_endpoint(
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = crud.get_story(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if not crud.can_view_story(db, story, user.id):
        raise HTTPException(status_code=403, detail="Not allowed to view")

    if user.id != story.author_id:
        if crud.record_view(db, story, user.id):
            db.commit()
    db.refresh(story)
    return _serialize_story(db, story, user)


@router.post("/{story_id}/view", response_model=StoryOut)
def mark_story_viewed(
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = crud.get_story(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if not crud.can_view_story(db, story, user.id):
        raise HTTPException(status_code=403, detail="Not allowed to view")

    if user.id != story.author_id:
        crud.record_view(db, story, user.id)
        db.commit()
        db.refresh(story)
    return _serialize_story(db, story, user)


@router.get("/{story_id}/viewers", response_model=list[StoryViewerOut])
def story_viewers(
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = crud.get_story(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if story.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only author can see viewers")

    rows = crud.list_viewers(db, story_id)
    # реакции зрителей подмешиваем
    reactions = {
        r.user_id: r.emoji
        for r in db.query(StoryReaction).filter(StoryReaction.story_id == story_id).all()
    }
    return [
        StoryViewerOut(
            user_id=u.id,
            username=u.username,
            full_name=u.full_name,
            avatar_url=u.avatar_url,
            viewed_at=v.viewed_at,
            reaction=reactions.get(u.id),
        )
        for v, u in rows
    ]


# =====================================================================
#  Reactions
# =====================================================================

@router.post("/{story_id}/reaction", response_model=StoryOut)
def react_to_story(
    story_id: int,
    data: StoryReactionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = crud.get_story(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if not crud.can_view_story(db, story, user.id):
        raise HTTPException(status_code=403, detail="Not allowed")
    if not story.allow_reactions:
        raise HTTPException(status_code=403, detail="Reactions are disabled for this story")
    if story.author_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot react to your own story")

    crud.set_reaction(db, story, user.id, data.emoji)

    # уведомление автору
    n = notif_crud.create_notification(
        db, user_id=story.author_id, type="story_reaction",
        payload={
            "story_id": story.id,
            "from_user_id": user.id,
            "emoji": data.emoji,
        },
    )
    db.flush()
    db.commit()
    db.refresh(story)

    send_to_user_sync(story.author_id, EVT_NOTIFICATION, {
        "notification": {
            "id": n.id, "type": "story_reaction",
            "payload": n.payload, "is_read": False,
        }
    })
    return _serialize_story(db, story, user)


@router.delete("/{story_id}/reaction", response_model=StoryOut)
def remove_story_reaction(
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = crud.get_story(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    crud.remove_reaction(db, story, user.id)
    db.commit()
    db.refresh(story)
    return _serialize_story(db, story, user)


# =====================================================================
#  Reply (создаёт обычное private-сообщение автору)
# =====================================================================

@router.post("/{story_id}/reply")
def reply_to_story(
    story_id: int,
    data: StoryReplyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = crud.get_story(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if not story.allow_replies:
        raise HTTPException(status_code=403, detail="Replies are disabled for this story")
    if not crud.can_view_story(db, story, user.id):
        raise HTTPException(status_code=403, detail="Not allowed")
    if story.author_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot reply to your own story")

    chat = chats_crud.get_or_create_private_chat(db, user.id, story.author_id)
    msg = messages_crud.create_message(
        db, chat,
        sender_id=user.id,
        type=MessageType.story_reply,
        text=data.text,
    )
    db.commit()
    db.refresh(msg)

    from modules.messages.router import _serialize_one
    out = _serialize_one(db, msg)
    broadcast_to_chat_sync(db, chat.id, EVT_NEW_MESSAGE, {"message": out.model_dump(mode="json")})

    n = notif_crud.create_notification(
        db, user_id=story.author_id, type="story_reply",
        chat_id=chat.id, message_id=msg.id,
        payload={
            "story_id": story.id,
            "from_user_id": user.id,
            "preview": data.text[:100],
        },
    )
    db.flush()
    db.commit()
    send_to_user_sync(story.author_id, EVT_NOTIFICATION, {
        "notification": {"id": n.id, "type": "story_reply", "payload": n.payload, "is_read": False}
    })

    return {
        "chat_id": chat.id,
        "message_id": msg.id,
    }


# =====================================================================
#  Close friends
# =====================================================================

@router.get("/close-friends", response_model=CloseFriendsOut)
def get_close_friends(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return CloseFriendsOut(user_ids=crud.list_close_friends(db, user.id))


@router.put("/close-friends", response_model=CloseFriendsOut)
def update_close_friends(
    data: CloseFriendsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    final = crud.set_close_friends(db, user.id, data.user_ids)
    db.commit()
    return CloseFriendsOut(user_ids=final)
