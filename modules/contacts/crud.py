"""CRUD контактов."""
from sqlalchemy.orm import Session

from models import Contact, User


def get_contact(db: Session, owner_id: int, contact_id: int) -> Contact | None:
    return (
        db.query(Contact)
        .filter(Contact.owner_id == owner_id, Contact.contact_id == contact_id)
        .first()
    )


def list_contacts(db: Session, owner_id: int) -> list[tuple[Contact, User]]:
    return (
        db.query(Contact, User)
        .join(User, User.id == Contact.contact_id)
        .filter(Contact.owner_id == owner_id, User.is_active.is_(True))
        .order_by(User.full_name.asc().nullslast(), User.username.asc())
        .all()
    )


def add_contact(
    db: Session,
    *,
    owner_id: int,
    contact_id: int,
    custom_first_name: str | None = None,
    custom_last_name: str | None = None,
) -> Contact:
    existing = get_contact(db, owner_id, contact_id)
    if existing:
        if custom_first_name is not None:
            existing.custom_first_name = custom_first_name
        if custom_last_name is not None:
            existing.custom_last_name = custom_last_name
        existing.is_mutual = bool(get_contact(db, contact_id, owner_id))
        return existing

    contact = Contact(
        owner_id=owner_id,
        contact_id=contact_id,
        custom_first_name=custom_first_name,
        custom_last_name=custom_last_name,
        is_mutual=bool(get_contact(db, contact_id, owner_id)),
    )
    db.add(contact)

    # обновим взаимность у второй стороны
    reverse = get_contact(db, contact_id, owner_id)
    if reverse:
        reverse.is_mutual = True

    return contact


def update_contact(
    db: Session,
    *,
    owner_id: int,
    contact_id: int,
    custom_first_name: str | None = None,
    custom_last_name: str | None = None,
) -> Contact | None:
    contact = get_contact(db, owner_id, contact_id)
    if not contact:
        return None
    if custom_first_name is not None:
        contact.custom_first_name = custom_first_name
    if custom_last_name is not None:
        contact.custom_last_name = custom_last_name
    return contact


def remove_contact(db: Session, owner_id: int, contact_id: int) -> bool:
    contact = get_contact(db, owner_id, contact_id)
    if not contact:
        return False
    db.delete(contact)
    # снимаем взаимность у второй стороны
    reverse = get_contact(db, contact_id, owner_id)
    if reverse:
        reverse.is_mutual = False
    return True


def find_users_by_phones(db: Session, phones: list[str]) -> list[User]:
    """Возвращает зарегистрированных пользователей по списку телефонов."""
    if not phones:
        return []
    return db.query(User).filter(User.phone.in_(phones), User.is_active.is_(True)).all()


def is_contact(db: Session, owner_id: int, target_id: int) -> bool:
    return get_contact(db, owner_id, target_id) is not None
