"""HTTP API уведомлений."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models import get_db, User
from dependencies import get_current_user

from modules.notifications import crud
from modules.notifications.schemas import NotificationOut, UnreadCountOut


router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationOut])
def my_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return crud.list_notifications(
        db, user.id, unread_only=unread_only, limit=limit, before_id=before_id
    )


@router.get("/unread-count", response_model=UnreadCountOut)
def my_unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    total, by_type = crud.unread_count(db, user.id)
    return UnreadCountOut(total=total, by_type=by_type)


@router.post("/{notif_id}/read")
def mark_one_read(
    notif_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not crud.mark_read(db, user.id, notif_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    db.commit()
    return {"detail": "Marked"}


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = crud.mark_all_read(db, user.id)
    db.commit()
    return {"marked": count}


@router.delete("/{notif_id}")
def delete_notification(
    notif_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not crud.delete_notification(db, user.id, notif_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    db.commit()
    return {"detail": "Deleted"}
