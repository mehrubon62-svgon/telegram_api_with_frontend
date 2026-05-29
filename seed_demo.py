"""
Seed реалистичных демо-данных для UI-теста:
  - ~14 юзеров (только @username + телефон)
  - контакты (взаимные)
  - 2 группы и 1 канал
  - реалистичные диалоги в private-чатах за последние 5 дней
  - сообщения в группах с разными отправителями
  - реакции на ключевые сообщения
  - закреплённое сообщение в одной из групп

Скрипт идемпотентный по email/телефону: если юзер уже есть, реюзает.
"""
import random
from datetime import datetime, timedelta, timezone
from itertools import combinations

from sqlalchemy.orm import Session

from models import (
    SessionLocal,
    User,
    Chat,
    ChatType,
    ChatMember,
    ChatMemberRole,
    Message,
    MessageType,
    MessageReaction,
    PinnedMessage,
    Contact,
    PrivacySetting,
)
from modules.users import crud as users_crud


random.seed(42)


# ============================================================
#  Юзеры (telegram-style: username + phone)
# ============================================================

USERS = [
    ("alex", "+12025550100", "Software developer. Coffee + code."),
    ("maria", "+34911223344", "Designer. Always sketching."),
    ("kenji", "+819012345678", "Tokyo • Photography • Cats"),
    ("sofia", "+393331234567", "Pasta and product management."),
    ("oliver", "+447700900123", "Music producer. Vinyl collector."),
    ("ananya", "+919876543210", "ML engineer. Cricket fan."),
    ("dmitry", "+79161234567", "Backend dev. Lifting weights."),
    ("emma", "+33612345678", "Travel blogger. Currently in Lisbon."),
    ("lukas", "+491701234567", "Berlin techno. Berghain enjoyer."),
    ("yuki", "+821012345678", "Streamer • Esports"),
    ("rafael", "+5511987654321", "Football, samba, and bossa nova."),
    ("chen", "+8613812345678", "Open source maintainer."),
    ("noah", "+15551234567", "Just here for the memes."),
    ("ivy", "+61412345678", "Sydney • Marine biologist."),
]


def upsert_user(db: Session, username: str, phone: str, bio: str) -> User:
    existing = users_crud.get_user_by_username(db, username)
    if existing:
        if not existing.bio:
            existing.bio = bio
        return existing
    # email-заглушка: телефон без + и нечисловых
    digits = "".join(ch for ch in phone if ch.isdigit())
    email = f"{digits}@tg.local"
    if users_crud.get_user_by_email(db, email):
        return users_crud.get_user_by_email(db, email)
    user = users_crud.create_user(
        db,
        email=email,
        password="demo1234",
        username=username,
        phone=phone,
    )
    user.bio = bio
    db.commit()
    db.refresh(user)
    return user


# ============================================================
#  Чат-конструкторы
# ============================================================

def get_or_make_private(db: Session, a: User, b: User) -> Chat:
    """Личный чат между двумя юзерами; реюзает существующий."""
    sub_a = db.query(ChatMember.chat_id).filter(ChatMember.user_id == a.id)
    sub_b = db.query(ChatMember.chat_id).filter(ChatMember.user_id == b.id)
    chat = (
        db.query(Chat)
        .filter(
            Chat.type == ChatType.private,
            Chat.id.in_(sub_a),
            Chat.id.in_(sub_b),
        )
        .first()
    )
    if chat:
        return chat
    chat = Chat(type=ChatType.private, creator_id=a.id, members_count=2)
    db.add(chat)
    db.flush()
    db.add(ChatMember(chat_id=chat.id, user_id=a.id, role=ChatMemberRole.member))
    db.add(ChatMember(chat_id=chat.id, user_id=b.id, role=ChatMemberRole.member))
    return chat


def make_group(db: Session, title: str, creator: User, members: list[User], description: str | None = None) -> Chat:
    chat = Chat(
        type=ChatType.group,
        title=title,
        description=description,
        creator_id=creator.id,
        members_count=0,
    )
    db.add(chat)
    db.flush()
    db.add(ChatMember(chat_id=chat.id, user_id=creator.id, role=ChatMemberRole.creator))
    chat.members_count = 1
    for u in members:
        if u.id == creator.id:
            continue
        db.add(ChatMember(chat_id=chat.id, user_id=u.id, role=ChatMemberRole.member, invited_by_id=creator.id))
        chat.members_count += 1
    return chat


def make_channel(db: Session, title: str, creator: User, subscribers: list[User], username: str, description: str) -> Chat:
    chat = Chat(
        type=ChatType.channel,
        title=title,
        description=description,
        public_username=username,
        creator_id=creator.id,
        can_send_messages=False,
        members_count=0,
    )
    db.add(chat)
    db.flush()
    db.add(ChatMember(chat_id=chat.id, user_id=creator.id, role=ChatMemberRole.creator))
    chat.members_count = 1
    for u in subscribers:
        if u.id == creator.id:
            continue
        db.add(ChatMember(chat_id=chat.id, user_id=u.id, role=ChatMemberRole.member, invited_by_id=creator.id))
        chat.members_count += 1
    return chat


# ============================================================
#  Сообщения
# ============================================================

def push_msg(
    db: Session,
    chat: Chat,
    sender: User,
    text: str,
    *,
    minutes_ago: int,
    reply_to_id: int | None = None,
) -> Message:
    created = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    msg = Message(
        chat_id=chat.id,
        sender_id=sender.id,
        type=MessageType.text,
        text=text,
        reply_to_id=reply_to_id,
        created_at=created,
    )
    db.add(msg)
    db.flush()
    chat.last_message_id = msg.id
    return msg


# ============================================================
#  Сценарии
# ============================================================

PRIVATE_DIALOGS = {
    ("alex", "maria"): [
        ("alex", "hey, are you on for the design review tomorrow?"),
        ("maria", "yep, 11am yeah?"),
        ("alex", "10:30 actually, sorry, calendar fight"),
        ("maria", "ok pushing it. need anything from me before?"),
        ("alex", "would love a one-pager on the new flow"),
        ("maria", "on it. send by tonight"),
        ("alex", "you're a star"),
        ("maria", "i know"),
    ],
    ("alex", "dmitry"): [
        ("dmitry", "did the migration run on staging?"),
        ("alex", "yes. one warning about a fk cycle, otherwise green"),
        ("dmitry", "fk cycle is fine for sqlite, postgres handles it"),
        ("alex", "i'll add a note in the README"),
        ("dmitry", "good. coffee at 4?"),
        ("alex", "always"),
    ],
    ("alex", "emma"): [
        ("emma", "guess where i am"),
        ("alex", "...lisbon?"),
        ("emma", "you stalker"),
        ("emma", "the food here is unreal. pasteis de nata for breakfast 4 days running"),
        ("alex", "send pictures or it didn't happen"),
        ("emma", "next time you're invited"),
    ],
    ("alex", "kenji"): [
        ("kenji", "got the camera back from repair"),
        ("alex", "the canon?"),
        ("kenji", "yeah. shutter was sticking. shooting again tomorrow"),
        ("alex", "let me know if you post anything new"),
    ],
    ("alex", "ananya"): [
        ("ananya", "did you read the embeddings paper i sent?"),
        ("alex", "skimmed it. the eval section is sus"),
        ("ananya", "totally agreed. they cherry-picked benchmarks"),
        ("alex", "will respond properly tonight"),
    ],
    ("alex", "sofia"): [
        ("sofia", "pm sync moved to thursday btw"),
        ("alex", "noted"),
        ("sofia", "thanks. also: roadmap doc up — please look"),
        ("alex", "will do tonight"),
    ],
    ("alex", "noah"): [
        ("noah", "look what i found"),
        ("noah", "https://example.com/cat-typing.gif"),
        ("alex", "this is your contribution to society"),
        ("noah", "and i'm proud of it"),
    ],
}

GROUP_BACKEND = [
    ("dmitry", "team! standup in 5"),
    ("alex", "joining"),
    ("ananya", "remote today, audio only ok?"),
    ("dmitry", "fine"),
    ("alex", "PR #142 needs a second reviewer"),
    ("chen", "i'll take it after lunch"),
    ("dmitry", "we should probably bump the python version next sprint"),
    ("ananya", "+1, 3.13 has been solid"),
    ("alex", "agreed. i'll open a tracking issue"),
    ("dmitry", "there's a flaky test in messages module btw"),
    ("alex", "is that the websocket smoke?"),
    ("dmitry", "yeah"),
    ("alex", "i'll look. probably the lifespan/loop binding"),
    ("ananya", "@chen could you review the embedding service pr too when you have a sec"),
    ("chen", "yes after #142"),
    ("dmitry", "release note draft is in notion. add yours"),
    ("alex", "done"),
]

GROUP_DESIGN = [
    ("maria", "new chat-bubble specs are up. desktop and mobile both"),
    ("oliver", "looks tight. tail rendering on grouped messages — did you handle iOS Safari?"),
    ("maria", "yep, switched to inline svg masks"),
    ("ivy", "mobile spacing on day separators feels too tight"),
    ("maria", "noted, bumping to 12px"),
    ("yuki", "color tokens for dark mode look great. especially the own-message gradient"),
    ("maria", "thanks. it's a real telegram cyan-blue blend"),
    ("oliver", "voice waveform colors? we have those defined?"),
    ("maria", "still missing. opening a ticket"),
    ("ivy", "typography scale on small screens needs another pass imo"),
    ("maria", "i'll add another row of sizes for <360px"),
]

CHANNEL_NEWS = [
    ("noah", "Tech roundup — week 47"),
    ("noah", "1) New Vite 6 stable. Faster cold starts, better SSR. https://vitejs.dev"),
    ("noah", "2) React 19 RC ships actions and useOptimistic. The form story finally feels native."),
    ("noah", "3) Bun 1.2 — wider Node compat. They claim 100% jest API."),
    ("noah", "4) PostgreSQL 17 release notes are surprisingly heavy. JSON_TABLE() is in."),
    ("noah", "Pick of the week: tanstack/router v1 — file routing without next.js."),
]


# ============================================================
#  Запуск
# ============================================================

def main() -> None:
    db = SessionLocal()
    try:
        # 1) пользователи
        users: dict[str, User] = {}
        for username, phone, bio in USERS:
            users[username] = upsert_user(db, username, phone, bio)
        db.commit()
        print(f"users: {len(users)}")

        # privacy default — на всех создаст trigger в crud, но безопасно явно
        for u in users.values():
            if not db.query(PrivacySetting).filter(PrivacySetting.user_id == u.id).first():
                db.add(PrivacySetting(user_id=u.id))
        db.commit()

        # 2) контакты — пары "близких" друзей
        contact_pairs = [
            ("alex", "maria"), ("alex", "dmitry"), ("alex", "emma"),
            ("alex", "kenji"), ("alex", "ananya"), ("alex", "sofia"),
            ("maria", "oliver"), ("maria", "ivy"),
            ("dmitry", "ananya"), ("dmitry", "chen"),
            ("emma", "kenji"), ("emma", "lukas"),
            ("rafael", "yuki"), ("rafael", "noah"),
        ]
        for a_name, b_name in contact_pairs:
            a, b = users[a_name], users[b_name]
            if not db.query(Contact).filter(Contact.owner_id == a.id, Contact.contact_id == b.id).first():
                db.add(Contact(owner_id=a.id, contact_id=b.id, is_mutual=True))
            if not db.query(Contact).filter(Contact.owner_id == b.id, Contact.contact_id == a.id).first():
                db.add(Contact(owner_id=b.id, contact_id=a.id, is_mutual=True))
        db.commit()
        print(f"contacts: {len(contact_pairs) * 2}")

        # 3) приватные диалоги
        created_chats = 0
        for (a_name, b_name), lines in PRIVATE_DIALOGS.items():
            a, b = users[a_name], users[b_name]
            chat = get_or_make_private(db, a, b)
            db.flush()
            # пропустим, если в чате уже есть сообщения (повторный запуск)
            existing = db.query(Message).filter(Message.chat_id == chat.id).count()
            if existing >= len(lines):
                continue
            base = 60 * 6  # начнём 6 часов назад
            for i, (sender_name, text) in enumerate(lines):
                push_msg(db, chat, users[sender_name], text, minutes_ago=base - i * 7)
            created_chats += 1
        db.commit()
        print(f"private dialogs seeded: {created_chats}")

        # 4) группы
        backend = (
            db.query(Chat)
            .filter(Chat.type == ChatType.group, Chat.title == "Backend Team")
            .first()
        )
        if not backend:
            backend = make_group(
                db,
                "Backend Team",
                creator=users["dmitry"],
                members=[users[n] for n in ["alex", "ananya", "chen", "kenji"]],
                description="API, infra, releases.",
            )
            db.flush()
            base = 60 * 4
            for i, (sender, text) in enumerate(GROUP_BACKEND):
                push_msg(db, backend, users[sender], text, minutes_ago=base - i * 3)

            # закрепим важное сообщение
            pinned_msg = (
                db.query(Message)
                .filter(Message.chat_id == backend.id, Message.text.like("%release note draft%"))
                .first()
            )
            if pinned_msg:
                pinned_msg.is_pinned = True
                backend.pinned_message_id = pinned_msg.id
                db.add(PinnedMessage(chat_id=backend.id, message_id=pinned_msg.id, pinned_by_id=users["dmitry"].id))
            print("group: Backend Team")

        design = (
            db.query(Chat)
            .filter(Chat.type == ChatType.group, Chat.title == "Design Crit")
            .first()
        )
        if not design:
            design = make_group(
                db,
                "Design Crit",
                creator=users["maria"],
                members=[users[n] for n in ["oliver", "ivy", "yuki", "alex"]],
                description="Weekly design reviews.",
            )
            db.flush()
            base = 60 * 2
            for i, (sender, text) in enumerate(GROUP_DESIGN):
                push_msg(db, design, users[sender], text, minutes_ago=base - i * 4)
            print("group: Design Crit")

        # 5) канал
        channel = (
            db.query(Chat)
            .filter(Chat.type == ChatType.channel, Chat.public_username == "weeklytech")
            .first()
        )
        if not channel:
            channel = make_channel(
                db,
                title="Weekly Tech",
                creator=users["noah"],
                subscribers=[users[n] for n in ["alex", "maria", "dmitry", "ananya", "chen", "kenji", "sofia", "oliver", "ivy"]],
                username="weeklytech",
                description="Hand-picked weekly developer news.",
            )
            db.flush()
            base = 60 * 24
            for i, (sender, text) in enumerate(CHANNEL_NEWS):
                push_msg(db, channel, users[sender], text, minutes_ago=base - i * 30)
            print("channel: @weeklytech")

        db.commit()

        # 6) реакции — раскидаем разные на ключевые сообщения групп
        def add_reaction(message: Message, user: User, emoji: str) -> None:
            existing = (
                db.query(MessageReaction)
                .filter(
                    MessageReaction.message_id == message.id,
                    MessageReaction.user_id == user.id,
                    MessageReaction.emoji == emoji,
                )
                .first()
            )
            if not existing:
                db.add(MessageReaction(message_id=message.id, user_id=user.id, emoji=emoji))

        # реакции в группе Backend
        backend_msgs = (
            db.query(Message)
            .filter(Message.chat_id == backend.id)
            .order_by(Message.id.asc())
            .all()
        )
        if backend_msgs:
            # «we should probably bump the python version next sprint»
            target = next((m for m in backend_msgs if m.text and "bump the python" in m.text), None)
            if target:
                add_reaction(target, users["alex"], "👍")
                add_reaction(target, users["ananya"], "🔥")
                add_reaction(target, users["chen"], "🎉")
            # «release note draft is in notion. add yours»
            target = next((m for m in backend_msgs if m.text and "release note" in m.text), None)
            if target:
                add_reaction(target, users["alex"], "👍")
                add_reaction(target, users["ananya"], "👍")

        # реакции в Design
        design_msgs = (
            db.query(Message)
            .filter(Message.chat_id == design.id)
            .order_by(Message.id.asc())
            .all()
        )
        for m in design_msgs:
            if m.text and "telegram cyan-blue" in m.text:
                add_reaction(m, users["oliver"], "❤️")
                add_reaction(m, users["ivy"], "🔥")

        # реакции в канале
        channel_msgs = (
            db.query(Message)
            .filter(Message.chat_id == channel.id)
            .order_by(Message.id.asc())
            .all()
        )
        for m in channel_msgs[:3]:
            for u in random.sample(list(users.values()), 4):
                add_reaction(m, u, random.choice(["👍", "🔥", "👀", "❤️"]))

        db.commit()
        print("reactions added")

        print()
        print("=" * 50)
        print("DEMO LOGIN CREDENTIALS")
        print("=" * 50)
        print("Any of the seeded users; all share the same password.")
        print()
        print(f"  username:  @alex   (or any other)")
        print(f"  phone:     +12025550100")
        print(f"  password:  demo1234")
        print()
        print("Other usernames you can sign in as:")
        for u in USERS:
            print(f"  @{u[0]}  {u[1]}")
        print("=" * 50)
    finally:
        db.close()


if __name__ == "__main__":
    main()
