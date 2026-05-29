"""CRUD блокировок."""
from sqlalchemy.orm import Session

from models import Block, User


def is_blocked(db: Session, blocker_id: int, blocked_id: int) -> bool:
    return (
        db.query(Block)
        .filter(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
        .first()
        is not None
    )


def list_blocks(db: Session, blocker_id: int) -> list[tuple[Block, User]]:
    return (
        db.query(Block, User)
        .join(User, User.id == Block.blocked_id)
        .filter(Block.blocker_id == blocker_id)
        .order_by(Block.created_at.desc())
        .all()
    )


def add_block(db: Session, blocker_id: int, blocked_id: int) -> Block:
    existing = (
        db.query(Block)
        .filter(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
        .first()
    )
    if existing:
        return existing
    block = Block(blocker_id=blocker_id, blocked_id=blocked_id)
    db.add(block)
    return block


def remove_block(db: Session, blocker_id: int, blocked_id: int) -> bool:
    block = (
        db.query(Block)
        .filter(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
        .first()
    )
    if not block:
        return False
    db.delete(block)
    return True
