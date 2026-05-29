"""CRUD звонков."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import Call, CallParticipant, CallType, CallStatus, User


def utc() -> datetime:
    return datetime.now(timezone.utc)


def get_call(db: Session, call_id: int) -> Call | None:
    return db.query(Call).filter(Call.id == call_id).first()


def get_active_call_for_user(db: Session, user_id: int) -> Call | None:
    """Активный (не завершён) звонок, в который вовлечён пользователь."""
    return (
        db.query(Call)
        .join(CallParticipant, CallParticipant.call_id == Call.id)
        .filter(
            CallParticipant.user_id == user_id,
            Call.status.notin_([CallStatus.ended, CallStatus.declined, CallStatus.missed]),
        )
        .order_by(Call.started_at.desc())
        .first()
    )


def create_call(
    db: Session,
    *,
    initiator_id: int,
    type: CallType,
    is_video: bool,
    chat_id: int | None,
    is_group: bool,
    participant_ids: list[int],
) -> Call:
    call = Call(
        initiator_id=initiator_id,
        type=type,
        is_video=is_video,
        chat_id=chat_id,
        is_group=is_group,
        status=CallStatus.ringing,
        started_at=utc(),
    )
    db.add(call)
    db.flush()

    for uid in {*participant_ids, initiator_id}:
        joined = utc() if uid == initiator_id else None
        db.add(CallParticipant(
            call_id=call.id,
            user_id=uid,
            joined_at=joined,
        ))
    return call


def list_recent_calls(
    db: Session,
    user_id: int,
    *,
    limit: int = 50,
    missed_only: bool = False,
):
    q = (
        db.query(Call)
        .join(CallParticipant, CallParticipant.call_id == Call.id)
        .filter(CallParticipant.user_id == user_id)
    )
    if missed_only:
        q = q.filter(Call.status == CallStatus.missed)
    return q.order_by(Call.started_at.desc()).limit(limit).all()


def list_participants(db: Session, call_id: int) -> list[tuple[CallParticipant, User]]:
    return (
        db.query(CallParticipant, User)
        .join(User, User.id == CallParticipant.user_id)
        .filter(CallParticipant.call_id == call_id)
        .all()
    )


def get_participant(db: Session, call_id: int, user_id: int) -> CallParticipant | None:
    return (
        db.query(CallParticipant)
        .filter(CallParticipant.call_id == call_id, CallParticipant.user_id == user_id)
        .first()
    )


def accept_call(db: Session, call: Call, user_id: int) -> CallParticipant | None:
    p = get_participant(db, call.id, user_id)
    if not p:
        return None
    p.joined_at = utc()
    if call.status == CallStatus.ringing:
        call.status = CallStatus.accepted
        call.answered_at = utc()
    return p


def decline_call(db: Session, call: Call, user_id: int) -> bool:
    p = get_participant(db, call.id, user_id)
    if not p:
        return False
    p.left_at = utc()
    if not call.is_group:
        call.status = CallStatus.declined
        call.ended_at = utc()
    return True


def leave_call(db: Session, call: Call, user_id: int) -> None:
    p = get_participant(db, call.id, user_id)
    if p:
        p.left_at = utc()
    # Если не group и второй ушёл — звонок закончен.
    # Делаем flush, чтобы новое значение left_at попало в подсчёт.
    db.flush()
    if not call.is_group:
        active = (
            db.query(CallParticipant)
            .filter(CallParticipant.call_id == call.id, CallParticipant.left_at.is_(None))
            .count()
        )
        if active <= 1:
            end_call(db, call, end_reason="hang_up")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def end_call(db: Session, call: Call, *, end_reason: str | None = None) -> Call:
    if call.status not in (CallStatus.ended, CallStatus.declined, CallStatus.missed):
        call.ended_at = utc()
        answered = _aware(call.answered_at)
        if answered:
            call.status = CallStatus.ended
            call.duration_seconds = int((call.ended_at - answered).total_seconds())
        else:
            call.status = CallStatus.missed
        call.end_reason = end_reason
        # все unleft participants — left
        for p in db.query(CallParticipant).filter(
            CallParticipant.call_id == call.id, CallParticipant.left_at.is_(None)
        ).all():
            p.left_at = call.ended_at
    return call


def update_participant_state(
    db: Session,
    call_id: int,
    user_id: int,
    *,
    is_muted: bool | None = None,
    is_video_on: bool | None = None,
    is_screen_sharing: bool | None = None,
) -> CallParticipant | None:
    p = get_participant(db, call_id, user_id)
    if not p:
        return None
    if is_muted is not None:
        p.is_muted = is_muted
    if is_video_on is not None:
        p.is_video_on = is_video_on
    if is_screen_sharing is not None:
        p.is_screen_sharing = is_screen_sharing
    return p
