"""CRUD уведомлений + helper для создания из других модулей."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Notification


def create_notification(
    db: Session,
    *,
    user_id: int,
    type: str,
    chat_id: int | None = None,
    message_id: int | None = None,
    payload: dict | None = None,
) -> Notification:
    n = Notification(
        user_id=user_id,
        type=type,
        chat_id=chat_id,
        message_id=message_id,
        payload=payload,
    )
    db.add(n)
    return n


def list_notifications(
    db: Session,
    user_id: int,
    *,
    unread_only: bool = False,
    limit: int = 50,
    before_id: int | None = None,
) -> list[Notification]:
    q = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))
    if before_id is not None:
        q = q.filter(Notification.id < before_id)
    return q.order_by(Notification.id.desc()).limit(limit).all()


def get_notification(db: Session, user_id: int, notif_id: int) -> Notification | None:
    return (
        db.query(Notification)
        .filter(Notification.id == notif_id, Notification.user_id == user_id)
        .first()
    )


def mark_read(db: Session, user_id: int, notif_id: int) -> bool:
    n = get_notification(db, user_id, notif_id)
    if not n:
        return False
    n.is_read = True
    return True


def mark_all_read(db: Session, user_id: int) -> int:
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
        .update({"is_read": True}, synchronize_session=False)
    )
    return count


def delete_notification(db: Session, user_id: int, notif_id: int) -> bool:
    n = get_notification(db, user_id, notif_id)
    if not n:
        return False
    db.delete(n)
    return True


def unread_count(db: Session, user_id: int) -> tuple[int, dict[str, int]]:
    rows = (
        db.query(Notification.type, func.count(Notification.id))
        .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
        .group_by(Notification.type)
        .all()
    )
    by_type = {t: int(c) for t, c in rows}
    total = sum(by_type.values())
    return total, by_type
