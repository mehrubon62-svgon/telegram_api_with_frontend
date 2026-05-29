"""HTTP API блокировок."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models import get_db, User
from dependencies import get_current_user
from modules.users.crud import get_user_by_id

from modules.blocks import crud
from modules.blocks.schemas import BlockCreate, BlockOut


router = APIRouter(prefix="/blocks", tags=["Blocks"])


def _serialize(block, user) -> BlockOut:
    return BlockOut(
        id=block.id,
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        blocked_at=block.created_at,
    )


@router.get("", response_model=list[BlockOut])
def my_blocks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [_serialize(b, u) for b, u in crud.list_blocks(db, user.id)]


@router.post("", response_model=BlockOut, status_code=201)
def block_user(
    data: BlockCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if data.user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    target = get_user_by_id(db, data.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    block = crud.add_block(db, user.id, data.user_id)
    db.commit()
    db.refresh(block)
    return _serialize(block, target)


@router.delete("/{user_id}")
def unblock_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not crud.remove_block(db, user.id, user_id):
        raise HTTPException(status_code=404, detail="Not blocked")
    db.commit()
    return {"detail": "Unblocked"}
