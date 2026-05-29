"""HTTP API звонков.

Сервер делает signaling — обменивает SDP/ICE между участниками через
WebSocket-канал; реальный медиа-поток идёт по WebRTC P2P (или через
TURN, который тут не настраивается). Все события про звонок шлются
через WS как `call_*` события.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models import (
    get_db,
    User,
    CallStatus,
    CallType,
    ChatType,
)
from dependencies import get_current_user
from modules.users.crud import get_user_by_id
from modules.chats import crud as chats_crud
from modules.notifications import crud as notif_crud
from modules.websockets.events import send_to_user_sync, EVT_NOTIFICATION
from modules.websockets.manager import manager as ws_manager
import asyncio

from modules.calls import crud
from modules.calls.schemas import (
    CallStart,
    CallSignal,
    CallEnd,
    CallOut,
    CallParticipantOut,
    ParticipantStateUpdate,
)


router = APIRouter(prefix="/calls", tags=["Calls"])


# =====================================================================
#  WS-events
# =====================================================================

EVT_CALL_INCOMING = "call_incoming"
EVT_CALL_ACCEPTED = "call_accepted"
EVT_CALL_DECLINED = "call_declined"
EVT_CALL_ENDED = "call_ended"
EVT_CALL_PARTICIPANT_JOINED = "call_participant_joined"
EVT_CALL_PARTICIPANT_LEFT = "call_participant_left"
EVT_CALL_PARTICIPANT_UPDATED = "call_participant_updated"
EVT_CALL_SIGNAL = "call_signal"


def _push(user_ids: list[int], event: dict) -> None:
    """Шлёт событие списку пользователей через WS."""
    loop = ws_manager.loop
    if loop is None or not loop.is_running():
        return

    async def _send_now():
        await ws_manager.send_to_users(user_ids, event)

    asyncio.run_coroutine_threadsafe(_send_now(), loop)


# =====================================================================
#  Serialization
# =====================================================================

def _serialize_call(db: Session, call) -> CallOut:
    rows = crud.list_participants(db, call.id)
    return CallOut(
        id=call.id,
        chat_id=call.chat_id,
        initiator_id=call.initiator_id,
        type=call.type,
        status=call.status,
        is_video=call.is_video,
        is_group=call.is_group,
        started_at=call.started_at,
        answered_at=call.answered_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        end_reason=call.end_reason,
        participants=[
            CallParticipantOut(
                user_id=u.id,
                username=u.username,
                full_name=u.full_name,
                avatar_url=u.avatar_url,
                joined_at=p.joined_at,
                left_at=p.left_at,
                is_muted=p.is_muted,
                is_video_on=p.is_video_on,
                is_screen_sharing=p.is_screen_sharing,
            )
            for p, u in rows
        ],
    )


# =====================================================================
#  Start
# =====================================================================

@router.post("", response_model=CallOut, status_code=201)
def start_call(
    data: CallStart,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if data.callee_id is None and data.chat_id is None:
        raise HTTPException(status_code=400, detail="Either callee_id or chat_id is required")

    if data.callee_id is not None and data.callee_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot call yourself")

    # Проверка: уже в активном звонке?
    if crud.get_active_call_for_user(db, user.id):
        raise HTTPException(status_code=409, detail="Already in a call")

    if data.callee_id is not None:
        callee = get_user_by_id(db, data.callee_id)
        if not callee or not callee.is_active:
            raise HTTPException(status_code=404, detail="Callee not found")
        # blocks
        from modules.blocks import crud as blocks_crud
        if blocks_crud.is_blocked(db, callee.id, user.id) or blocks_crud.is_blocked(db, user.id, callee.id):
            raise HTTPException(status_code=403, detail="Calls are blocked between you")

        if crud.get_active_call_for_user(db, callee.id):
            raise HTTPException(status_code=409, detail="Callee is busy")

        call = crud.create_call(
            db,
            initiator_id=user.id,
            type=data.type,
            is_video=data.is_video,
            chat_id=None,
            is_group=False,
            participant_ids=[callee.id],
        )
        db.commit()
        db.refresh(call)

        # уведомления для вызываемого
        n = notif_crud.create_notification(
            db, user_id=callee.id, type="call_incoming",
            payload={"call_id": call.id, "from_user_id": user.id, "is_video": data.is_video},
        )
        db.commit()

        out = _serialize_call(db, call)
        _push([callee.id], {"type": EVT_CALL_INCOMING, "call": out.model_dump(mode="json")})
        send_to_user_sync(callee.id, EVT_NOTIFICATION, {
            "notification": {"id": n.id, "type": "call_incoming", "payload": n.payload, "is_read": False}
        })
        return out

    # group call (на основе чата)
    chat = chats_crud.get_chat(db, data.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.type not in (ChatType.group, ChatType.supergroup):
        raise HTTPException(status_code=400, detail="Group calls allowed in groups/supergroups only")

    member = chats_crud.get_member(db, chat.id, user.id)
    if not member or not chats_crud.is_active_member(member):
        raise HTTPException(status_code=403, detail="Not a member of this chat")

    member_ids = chats_crud.list_member_ids(db, chat.id)
    call = crud.create_call(
        db,
        initiator_id=user.id,
        type=data.type,
        is_video=data.is_video,
        chat_id=chat.id,
        is_group=True,
        participant_ids=member_ids,
    )
    db.commit()
    db.refresh(call)

    out = _serialize_call(db, call)
    _push(
        [uid for uid in member_ids if uid != user.id],
        {"type": EVT_CALL_INCOMING, "call": out.model_dump(mode="json")},
    )
    return out


# =====================================================================
#  Lifecycle
# =====================================================================

@router.post("/{call_id}/accept", response_model=CallOut)
def accept_call(
    call_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    call = crud.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.status in (CallStatus.ended, CallStatus.declined, CallStatus.missed):
        raise HTTPException(status_code=400, detail=f"Call is {call.status.value}")
    p = crud.accept_call(db, call, user.id)
    if not p:
        raise HTTPException(status_code=403, detail="Not invited to this call")
    db.commit()
    db.refresh(call)

    out = _serialize_call(db, call)
    rows = crud.list_participants(db, call.id)
    target_ids = [u.id for _, u in rows]
    _push(target_ids, {"type": EVT_CALL_PARTICIPANT_JOINED, "call_id": call.id, "user_id": user.id})
    if not call.is_group:
        _push(target_ids, {"type": EVT_CALL_ACCEPTED, "call": out.model_dump(mode="json")})
    return out


@router.post("/{call_id}/decline", response_model=CallOut)
def decline_call(
    call_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    call = crud.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if not crud.decline_call(db, call, user.id):
        raise HTTPException(status_code=403, detail="Not invited")
    db.commit()
    db.refresh(call)

    rows = crud.list_participants(db, call.id)
    target_ids = [u.id for _, u in rows]
    _push(target_ids, {"type": EVT_CALL_DECLINED, "call_id": call.id, "user_id": user.id})
    return _serialize_call(db, call)


@router.post("/{call_id}/leave", response_model=CallOut)
def leave_call(
    call_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    call = crud.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    crud.leave_call(db, call, user.id)
    db.commit()
    db.refresh(call)

    rows = crud.list_participants(db, call.id)
    target_ids = [u.id for _, u in rows]
    _push(target_ids, {"type": EVT_CALL_PARTICIPANT_LEFT, "call_id": call.id, "user_id": user.id})
    if call.status == CallStatus.ended:
        _push(target_ids, {"type": EVT_CALL_ENDED, "call_id": call.id, "duration": call.duration_seconds})
    return _serialize_call(db, call)


@router.post("/{call_id}/end", response_model=CallOut)
def end_call_endpoint(
    call_id: int,
    data: CallEnd | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    call = crud.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.initiator_id != user.id and not crud.get_participant(db, call_id, user.id):
        raise HTTPException(status_code=403, detail="Not allowed")
    crud.end_call(db, call, end_reason=data.end_reason if data else None)
    db.commit()
    db.refresh(call)

    rows = crud.list_participants(db, call.id)
    target_ids = [u.id for _, u in rows]
    _push(target_ids, {"type": EVT_CALL_ENDED, "call_id": call.id, "duration": call.duration_seconds})
    return _serialize_call(db, call)


# =====================================================================
#  Participant state (mute / video / screen-share)
# =====================================================================

@router.put("/{call_id}/state", response_model=CallOut)
def update_state(
    call_id: int,
    data: ParticipantStateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    call = crud.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    p = crud.update_participant_state(
        db, call_id, user.id,
        is_muted=data.is_muted, is_video_on=data.is_video_on,
        is_screen_sharing=data.is_screen_sharing,
    )
    if not p:
        raise HTTPException(status_code=403, detail="Not a participant")
    db.commit()
    db.refresh(call)

    rows = crud.list_participants(db, call.id)
    target_ids = [u.id for _, u in rows]
    _push(target_ids, {
        "type": EVT_CALL_PARTICIPANT_UPDATED,
        "call_id": call.id,
        "user_id": user.id,
        "is_muted": p.is_muted,
        "is_video_on": p.is_video_on,
        "is_screen_sharing": p.is_screen_sharing,
    })
    return _serialize_call(db, call)


# =====================================================================
#  WebRTC signaling (proxy)
# =====================================================================

@router.post("/{call_id}/signal")
def signal(
    call_id: int,
    data: CallSignal,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    call = crud.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if not crud.get_participant(db, call_id, user.id):
        raise HTTPException(status_code=403, detail="Not a participant")
    if not crud.get_participant(db, call_id, data.target_user_id):
        raise HTTPException(status_code=400, detail="Target is not a participant")

    _push([data.target_user_id], {
        "type": EVT_CALL_SIGNAL,
        "call_id": call.id,
        "from_user_id": user.id,
        "payload": data.payload,
    })
    return {"detail": "sent"}


# =====================================================================
#  History
# =====================================================================

@router.get("", response_model=list[CallOut])
def my_calls(
    missed_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = crud.list_recent_calls(db, user.id, limit=limit, missed_only=missed_only)
    return [_serialize_call(db, c) for c in items]


@router.get("/{call_id}", response_model=CallOut)
def get_call_endpoint(
    call_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    call = crud.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if not crud.get_participant(db, call_id, user.id):
        raise HTTPException(status_code=403, detail="Not allowed")
    return _serialize_call(db, call)
