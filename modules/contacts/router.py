"""HTTP API контактов."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models import get_db, User
from dependencies import get_current_user
from modules.users.crud import get_user_by_id

from modules.contacts import crud
from modules.contacts.schemas import (
    ContactCreate,
    ContactImportRequest,
    ContactUpdate,
    ContactOut,
)


router = APIRouter(prefix="/contacts", tags=["Contacts"])


def _serialize(contact, user) -> ContactOut:
    return ContactOut(
        id=contact.id,
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        phone=user.phone,
        avatar_url=user.avatar_url,
        custom_first_name=contact.custom_first_name,
        custom_last_name=contact.custom_last_name,
        is_mutual=contact.is_mutual,
        is_online=user.is_online,
        last_seen=user.last_seen,
        created_at=contact.created_at,
    )


@router.get("", response_model=list[ContactOut])
def my_contacts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = crud.list_contacts(db, user.id)
    return [_serialize(c, u) for c, u in rows]


@router.post("", response_model=ContactOut, status_code=201)
def add_my_contact(
    data: ContactCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if data.user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot add yourself")
    target = get_user_by_id(db, data.user_id)
    if not target or not target.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    contact = crud.add_contact(
        db,
        owner_id=user.id,
        contact_id=data.user_id,
        custom_first_name=data.custom_first_name,
        custom_last_name=data.custom_last_name,
    )
    db.commit()
    db.refresh(contact)
    return _serialize(contact, target)


@router.put("/{contact_user_id}", response_model=ContactOut)
def update_my_contact(
    contact_user_id: int,
    data: ContactUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contact = crud.update_contact(
        db,
        owner_id=user.id,
        contact_id=contact_user_id,
        custom_first_name=data.custom_first_name,
        custom_last_name=data.custom_last_name,
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.commit()
    db.refresh(contact)
    target = get_user_by_id(db, contact_user_id)
    return _serialize(contact, target)


@router.delete("/{contact_user_id}")
def remove_my_contact(
    contact_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not crud.remove_contact(db, user.id, contact_user_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    db.commit()
    return {"detail": "Removed"}


@router.post("/import", response_model=list[ContactOut])
def import_contacts(
    data: ContactImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Импорт телефонной книги. Возвращает только тех, кто уже есть в системе
    как зарегистрированный пользователь — их же сразу добавляем в контакты.
    """
    by_phone = {c.phone: c for c in data.contacts}
    found = crud.find_users_by_phones(db, list(by_phone.keys()))
    result = []
    for u in found:
        if u.id == user.id:
            continue
        item = by_phone.get(u.phone)
        contact = crud.add_contact(
            db,
            owner_id=user.id,
            contact_id=u.id,
            custom_first_name=item.first_name if item else None,
            custom_last_name=item.last_name if item else None,
        )
        result.append((contact, u))
    db.commit()
    for c, _ in result:
        db.refresh(c)
    return [_serialize(c, u) for c, u in result]
