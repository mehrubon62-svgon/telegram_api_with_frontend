"""
Богатый seed для демо: реальные аватары, фото-сторис, длинные живые диалоги,
больше чатов, реакции на множество сообщений, упоминания, расширенные био.

Идемпотентен — можно перезапускать.

Перед запуском бэк может работать. После запуска перелогинься в браузере
(F5 не достаточно — обнови чаты через выбор юзера).
"""
import os
import random
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from config import MEDIA_DIR
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
    Story,
    StoryPrivacyType,
    Attachment,
)
from modules.users import crud as users_crud


random.seed(2026)
NOW = datetime.now(timezone.utc)


# ============================================================
#  Helpers
# ============================================================

def utc_minus(minutes: int) -> datetime:
    return NOW - timedelta(minutes=minutes)


def upsert_user(db: Session, username: str, phone: str, bio: str, color: int) -> User:
    user = users_crud.get_user_by_username(db, username)
    if not user:
        digits = "".join(ch for ch in phone if ch.isdigit())
        email = f"{digits}@tg.local"
        existing = users_crud.get_user_by_email(db, email)
        if existing:
            user = existing
        else:
            user = users_crud.create_user(
                db, email=email, password="demo1234",
                username=username, phone=phone,
            )
    user.bio = bio
    user.name_color = color
    return user


def get_or_make_private(db: Session, a: User, b: User) -> Chat:
    sub_a = db.query(ChatMember.chat_id).filter(ChatMember.user_id == a.id)
    sub_b = db.query(ChatMember.chat_id).filter(ChatMember.user_id == b.id)
    chat = (
        db.query(Chat)
        .filter(Chat.type == ChatType.private, Chat.id.in_(sub_a), Chat.id.in_(sub_b))
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


def get_or_make_group(
    db: Session,
    title: str,
    creator: User,
    members: list[User],
    *,
    public_username: str,
    description: str,
    is_supergroup: bool = False,
) -> Chat:
    chat = (
        db.query(Chat)
        .filter(Chat.public_username == public_username)
        .first()
    )
    if chat:
        return chat
    chat = Chat(
        type=ChatType.supergroup if is_supergroup else ChatType.group,
        title=title,
        description=description,
        public_username=public_username,
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


def get_or_make_channel(
    db: Session,
    title: str,
    creator: User,
    subs: list[User],
    *,
    public_username: str,
    description: str,
) -> Chat:
    chat = (
        db.query(Chat)
        .filter(Chat.type == ChatType.channel, Chat.public_username == public_username)
        .first()
    )
    if chat:
        return chat
    chat = Chat(
        type=ChatType.channel,
        title=title,
        description=description,
        public_username=public_username,
        creator_id=creator.id,
        can_send_messages=False,
        members_count=0,
    )
    db.add(chat)
    db.flush()
    db.add(ChatMember(chat_id=chat.id, user_id=creator.id, role=ChatMemberRole.creator))
    chat.members_count = 1
    for u in subs:
        if u.id == creator.id:
            continue
        db.add(ChatMember(chat_id=chat.id, user_id=u.id, role=ChatMemberRole.member, invited_by_id=creator.id))
        chat.members_count += 1
    return chat


def push(
    db: Session,
    chat: Chat,
    sender: User,
    text: str | None,
    *,
    minutes_ago: int,
    reply_to_id: int | None = None,
    msg_type: MessageType = MessageType.text,
    attachments: list[dict] | None = None,
) -> Message:
    msg = Message(
        chat_id=chat.id,
        sender_id=sender.id,
        type=msg_type,
        text=text,
        reply_to_id=reply_to_id,
        created_at=utc_minus(minutes_ago),
    )
    db.add(msg)
    db.flush()
    if attachments:
        for a in attachments:
            db.add(Attachment(message_id=msg.id, **a))
    chat.last_message_id = msg.id
    return msg


def add_reactions(db: Session, message: Message, emoji_to_users: dict[str, list[User]]) -> None:
    for emoji, users in emoji_to_users.items():
        for u in users:
            existing = (
                db.query(MessageReaction)
                .filter(
                    MessageReaction.message_id == message.id,
                    MessageReaction.user_id == u.id,
                    MessageReaction.emoji == emoji,
                )
                .first()
            )
            if not existing:
                db.add(MessageReaction(message_id=message.id, user_id=u.id, emoji=emoji))


# ============================================================
#  Скачиваем «реальные» картинки для аватаров и сторис
# ============================================================

def download_image(url: str, target_rel: str) -> str:
    """Скачивает картинку в MEDIA_DIR/target_rel, возвращает public-url."""
    target_path = Path(MEDIA_DIR) / target_rel
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not target_path.exists() or target_path.stat().st_size < 1024:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                target_path.write_bytes(resp.read())
        except Exception as e:
            print(f"  [warn] failed to download {url}: {e}")
            return ""
    return f"/media-files/{target_rel}"


def picsum_avatar(seed: str) -> str:
    return f"https://picsum.photos/seed/{seed}/256/256"


def picsum_story(seed: str) -> str:
    return f"https://picsum.photos/seed/{seed}/720/1280"


# ============================================================
#  Контент диалогов
# ============================================================

USERS_DATA = [
    # username, phone, bio, name_color
    ("alex", "+12025550100", "Software developer. Coffee + code.", 5),
    ("maria", "+34911223344", "Designer. Always sketching.", 6),
    ("kenji", "+819012345678", "Tokyo · Photography · Cats.", 1),
    ("sofia", "+393331234567", "Pasta and product management.", 0),
    ("oliver", "+447700900123", "Music producer. Vinyl collector.", 9),
    ("ananya", "+919876543210", "ML engineer. Cricket fan.", 2),
    ("dmitry", "+79161234567", "Backend dev. Lifting weights.", 8),
    ("emma", "+33612345678", "Travel blogger. Currently in Lisbon.", 3),
    ("lukas", "+491701234567", "Berlin techno. Berghain enjoyer.", 10),
    ("yuki", "+821012345678", "Streamer · Esports.", 6),
    ("rafael", "+5511987654321", "Football, samba, bossa nova.", 4),
    ("chen", "+8613812345678", "Open source maintainer.", 7),
    ("noah", "+15551234567", "Just here for the memes.", 11),
    ("ivy", "+61412345678", "Sydney · Marine biologist.", 3),
    ("liam", "+35389111222", "Dublin. Pints and rugby.", 5),
    ("zara", "+9665011112233", "Architect, runner.", 6),
]


# Контакты (взаимные)
CONTACT_PAIRS = [
    ("alex", "maria"), ("alex", "dmitry"), ("alex", "emma"), ("alex", "kenji"),
    ("alex", "ananya"), ("alex", "sofia"), ("alex", "noah"), ("alex", "ivy"),
    ("maria", "oliver"), ("maria", "ivy"),
    ("dmitry", "ananya"), ("dmitry", "chen"),
    ("emma", "kenji"), ("emma", "lukas"),
    ("rafael", "yuki"), ("rafael", "noah"),
    ("liam", "zara"), ("zara", "alex"),
]


# Тысячные диалоги, делаю по-настоящему длинными
DIALOG_AM = [
    ("alex", "morning. did you push the design for the chat bubbles?"),
    ("maria", "pushed last night. there's a separate branch for the dark variant"),
    ("alex", "yeah saw it. one thing — the time inside the bubble is hard to read on the gradient"),
    ("maria", "i lowered the opacity to 0.7. should be fine on most images"),
    ("alex", "let me try with a real screenshot first"),
    ("maria", "ok. ping me when you have something"),
    ("alex", "btw have you seen the new sticker pack telegram dropped?"),
    ("maria", "the one with the cats? yes. addicted already"),
    ("alex", "obviously"),
    ("maria", "lol"),
    ("alex", "speaking of — should we also do reaction animations? hover ones?"),
    ("maria", "yes. i'll mock something tonight"),
    ("alex", "you legend"),
    ("maria", "i know"),
    ("alex", "what's the eta for the rebrand spec?"),
    ("maria", "friday at the latest"),
    ("alex", "amazing. okay back to standup"),
    ("maria", "good luck"),
]

DIALOG_AD = [
    ("dmitry", "morning"),
    ("alex", "morning"),
    ("dmitry", "the deploy went through, all green"),
    ("alex", "perfect. any flaky tests?"),
    ("dmitry", "the websocket smoke is still misbehaving once in a while"),
    ("alex", "i'll look today"),
    ("dmitry", "appreciate it"),
    ("alex", "btw lunch?"),
    ("dmitry", "ramen?"),
    ("alex", "always"),
    ("dmitry", "12:30"),
    ("alex", "👌"),
]

DIALOG_AE = [
    ("emma", "guess where i am"),
    ("alex", "lisbon"),
    ("emma", "you stalker"),
    ("emma", "the food here is unreal. pasteis de nata for breakfast 4 days in a row"),
    ("alex", "send pictures or it didn't happen"),
    ("emma", "incoming"),
    # это сообщение получит вложение
    ("emma", "[photo: pasteis]"),
    ("alex", "now i'm hungry"),
    ("emma", "told you"),
]

DIALOG_AK = [
    ("kenji", "got the camera back from repair"),
    ("alex", "the canon?"),
    ("kenji", "yeah. shutter was sticking. shooting again tomorrow"),
    ("alex", "if you go to that lookout, send a photo"),
    ("kenji", "will do"),
    ("kenji", "[photo: tokyo skyline]"),
    ("alex", "this is unreal"),
]

DIALOG_AAN = [
    ("ananya", "did you read the embeddings paper i sent?"),
    ("alex", "skimmed it. their eval section is sus"),
    ("ananya", "totally agreed"),
    ("ananya", "they cherry-picked benchmarks"),
    ("alex", "right. i'll write a proper comment tonight"),
    ("ananya", "thanks"),
]

DIALOG_AS = [
    ("sofia", "pm sync moved to thursday"),
    ("alex", "noted"),
    ("sofia", "and the roadmap doc is up. please look"),
    ("alex", "will do tonight"),
    ("sofia", "pinned in the channel"),
    ("alex", "👍"),
]

DIALOG_AN = [
    ("noah", "look what i found"),
    ("noah", "https://example.com/cat-typing.gif"),
    ("alex", "this is your contribution to society"),
    ("noah", "and i'm proud of it"),
    ("noah", "anyway, working on a new project"),
    ("alex", "?"),
    ("noah", "telegram clone"),
    ("alex", "lmao"),
]

DIALOG_AI = [
    ("ivy", "you'll like this"),
    ("ivy", "[photo: reef shark]"),
    ("alex", "is that a reef shark"),
    ("ivy", "yes. great barrier reef"),
    ("alex", "i need to come visit you one of these days"),
    ("ivy", "you're always welcome"),
]


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
    ("dmitry", "thanks all"),
]

GROUP_DESIGN = [
    ("maria", "new chat-bubble specs are up. desktop and mobile both"),
    ("oliver", "looks tight. tail rendering on grouped messages — did you handle iOS Safari?"),
    ("maria", "yep, switched to inline svg masks"),
    ("ivy", "mobile spacing on day separators feels too tight"),
    ("maria", "noted, bumping to 12px"),
    ("yuki", "color tokens for dark mode look great. especially the own-message gradient"),
    ("maria", "thanks. real telegram cyan-blue blend"),
    ("oliver", "voice waveform colors? we have those defined?"),
    ("maria", "still missing. opening a ticket"),
    ("ivy", "typography scale on small screens needs another pass imo"),
    ("maria", "i'll add another row of sizes for <360px"),
    ("oliver", "story progress segments — there's a small jitter on the active one"),
    ("maria", "i think it's because i'm using transition on the active too. let me fix"),
    ("ivy", "👀"),
]

GROUP_NEARBY = [
    ("liam", "anyone going to the meetup tomorrow"),
    ("zara", "yes"),
    ("emma", "i'll be there"),
    ("liam", "great. usual pub after?"),
    ("zara", "always"),
    ("emma", "i'll bring the people"),
    ("liam", "🍻"),
]

CHANNEL_NEWS = [
    ("noah", "Tech roundup — week 47"),
    ("noah", "1) Vite 6 stable. Faster cold starts, better SSR."),
    ("noah", "2) React 19 RC ships actions and useOptimistic. The form story finally feels native."),
    ("noah", "3) Bun 1.2 — wider Node compat. They claim 100% jest API."),
    ("noah", "4) PostgreSQL 17 release notes are surprisingly heavy. JSON_TABLE() is in."),
    ("noah", "Pick of the week: tanstack/router v1 — file routing without next.js."),
    ("noah", "Reading list — share what you're enjoying in the comments."),
]


# ============================================================
#  Stories
# ============================================================

STORIES_PLAN = [
    # username, caption, seed для картинки
    ("emma", "Lisbon mornings.", "lisbon"),
    ("emma", "Pasteis #5 of the week.", "pastry"),
    ("kenji", "Yokohama at dusk.", "yokohama"),
    ("kenji", "Tonight's setup.", "kenji_camera"),
    ("ivy", "Reef day.", "reef"),
    ("ivy", "Friend.", "turtle"),
    ("maria", "New stickers in progress.", "stickers"),
    ("oliver", "Studio session.", "studio"),
    ("rafael", "Game day.", "stadium"),
    ("yuki", "Stream tonight at 8.", "stream"),
    ("alex", "Saved messages.", "code"),
    ("noah", "Friday.", "friday"),
]


# ============================================================
#  Запуск
# ============================================================

def main() -> None:
    db = SessionLocal()
    try:
        # 1) Юзеры (+ аватары)
        users: dict[str, User] = {}
        print("seeding users…")
        for u, phone, bio, color in USERS_DATA:
            user = upsert_user(db, u, phone, bio, color)
            users[u] = user
        db.commit()

        print("downloading avatars…")
        for u in users.values():
            if u.avatar_url and Path(MEDIA_DIR + (u.avatar_url.replace("/media-files/", "/"))).exists():
                continue
            url = picsum_avatar(u.username or str(u.id))
            local = download_image(url, f"avatars/{u.id}/seed.jpg")
            if local:
                u.avatar_url = local
        db.commit()

        # 2) Контакты
        print("contacts…")
        for a_name, b_name in CONTACT_PAIRS:
            a, b = users[a_name], users[b_name]
            if not db.query(Contact).filter(Contact.owner_id == a.id, Contact.contact_id == b.id).first():
                db.add(Contact(owner_id=a.id, contact_id=b.id, is_mutual=True))
            if not db.query(Contact).filter(Contact.owner_id == b.id, Contact.contact_id == a.id).first():
                db.add(Contact(owner_id=b.id, contact_id=a.id, is_mutual=True))
        db.commit()

        # 3) Приватные диалоги
        print("dialogs…")
        for tag, lines in [
            (("alex", "maria"), DIALOG_AM),
            (("alex", "dmitry"), DIALOG_AD),
            (("alex", "emma"), DIALOG_AE),
            (("alex", "kenji"), DIALOG_AK),
            (("alex", "ananya"), DIALOG_AAN),
            (("alex", "sofia"), DIALOG_AS),
            (("alex", "noah"), DIALOG_AN),
            (("alex", "ivy"), DIALOG_AI),
        ]:
            a, b = users[tag[0]], users[tag[1]]
            chat = get_or_make_private(db, a, b)
            db.flush()
            existing = db.query(Message).filter(Message.chat_id == chat.id).count()
            if existing >= len(lines):
                continue
            base = 60 * 5
            for i, (sname, text) in enumerate(lines):
                if text.startswith("[photo:"):
                    seed = text.split("[photo:", 1)[1].rstrip("]").strip().replace(" ", "_")
                    local = download_image(picsum_story(seed), f"photos/seed/{seed}.jpg")
                    if local:
                        push(
                            db, chat, users[sname], None,
                            minutes_ago=base - i * 4,
                            msg_type=MessageType.photo,
                            attachments=[{
                                "file_url": local,
                                "mime_type": "image/jpeg",
                                "width": 720,
                                "height": 1280,
                                "size_bytes": Path(MEDIA_DIR + local.replace("/media-files/", "/")).stat().st_size,
                            }],
                        )
                else:
                    push(db, chat, users[sname], text, minutes_ago=base - i * 4)
        db.commit()

        # 4) Группы
        print("groups…")
        backend = get_or_make_group(
            db, "Backend Team", users["dmitry"],
            [users[n] for n in ["alex", "ananya", "chen", "kenji"]],
            public_username="backend_team",
            description="API, infra, releases.",
        )
        db.flush()
        if db.query(Message).filter(Message.chat_id == backend.id).count() == 0:
            base = 60 * 4
            for i, (sname, text) in enumerate(GROUP_BACKEND):
                push(db, backend, users[sname], text, minutes_ago=base - i * 3)
            # закрепим важное
            release_msg = (
                db.query(Message)
                .filter(Message.chat_id == backend.id, Message.text.like("%release note draft%"))
                .first()
            )
            if release_msg:
                release_msg.is_pinned = True
                backend.pinned_message_id = release_msg.id
                db.add(PinnedMessage(chat_id=backend.id, message_id=release_msg.id, pinned_by_id=users["dmitry"].id))

        design = get_or_make_group(
            db, "Design Crit", users["maria"],
            [users[n] for n in ["oliver", "ivy", "yuki", "alex"]],
            public_username="design_crit",
            description="Weekly design reviews.",
        )
        db.flush()
        if db.query(Message).filter(Message.chat_id == design.id).count() == 0:
            base = 60 * 2
            for i, (sname, text) in enumerate(GROUP_DESIGN):
                push(db, design, users[sname], text, minutes_ago=base - i * 4)

        nearby = get_or_make_group(
            db, "Dublin Devs", users["liam"],
            [users[n] for n in ["zara", "emma", "alex"]],
            public_username="dublin_devs",
            description="Local meetups.",
        )
        db.flush()
        if db.query(Message).filter(Message.chat_id == nearby.id).count() == 0:
            base = 60
            for i, (sname, text) in enumerate(GROUP_NEARBY):
                push(db, nearby, users[sname], text, minutes_ago=base - i * 5)

        db.commit()

        # 5) Канал + связь с группой
        print("channel…")
        channel = get_or_make_channel(
            db, "Weekly Tech", users["noah"],
            [users[n] for n in ["alex", "maria", "dmitry", "ananya", "chen", "kenji", "sofia", "oliver", "ivy", "liam", "zara"]],
            public_username="weeklytech",
            description="Hand-picked weekly developer news.",
        )
        if not channel.linked_chat_id:
            channel.linked_chat_id = backend.id
        db.flush()
        if db.query(Message).filter(Message.chat_id == channel.id).count() == 0:
            base = 60 * 24
            for i, (sname, text) in enumerate(CHANNEL_NEWS):
                push(db, channel, users[sname], text, minutes_ago=base - i * 30)
        db.commit()

        # 6) Реакции
        print("reactions…")

        def find_msg(chat: Chat, contains: str) -> Message | None:
            return (
                db.query(Message)
                .filter(Message.chat_id == chat.id, Message.text.like(f"%{contains}%"))
                .first()
            )

        m = find_msg(backend, "bump the python")
        if m:
            add_reactions(db, m, {
                "👍": [users["alex"], users["ananya"]],
                "🔥": [users["chen"]],
            })

        m = find_msg(backend, "release note draft")
        if m:
            add_reactions(db, m, {"👍": [users["alex"], users["ananya"]]})

        m = find_msg(design, "telegram cyan-blue")
        if m:
            add_reactions(db, m, {
                "❤️": [users["oliver"], users["ivy"]],
                "🔥": [users["yuki"]],
            })

        m = find_msg(design, "story progress segments")
        if m:
            add_reactions(db, m, {"😂": [users["alex"], users["ivy"]]})

        # реакции в канале — много разных
        for m in db.query(Message).filter(Message.chat_id == channel.id).all():
            if not m.text:
                continue
            for u in random.sample(list(users.values()), random.randint(2, 5)):
                add_reactions(db, m, {random.choice(["👍", "🔥", "❤️", "👀", "🙌"]): [u]})

        # 7) Stories
        print("stories…")
        # удалим истёкшие/повторно создавать не будем
        existing_story_seeds = {
            (s.author_id, s.media_url): True
            for s in db.query(Story).all()
        }
        for username, caption, seed in STORIES_PLAN:
            user = users[username]
            url = picsum_story(seed)
            local = download_image(url, f"stories/{user.id}/{seed}.jpg")
            if not local:
                continue
            key = (user.id, local)
            if key in existing_story_seeds:
                continue
            db.add(Story(
                author_id=user.id,
                media_url=local,
                media_type="photo",
                caption=caption,
                privacy=StoryPrivacyType.everybody,
                width=720,
                height=1280,
                expires_at=NOW + timedelta(hours=20),  # истечёт через 20 часов
                created_at=NOW - timedelta(minutes=random.randint(10, 600)),
            ))
        db.commit()

        # 8) name color уже сидим в upsert_user — обновим существующих
        for u in users.values():
            for nu, _, _, color in USERS_DATA:
                if u.username == nu:
                    u.name_color = color
                    break
        db.commit()

        # ----------------- summary -----------------
        n_users = db.query(User).count()
        n_chats = db.query(Chat).count()
        n_msgs = db.query(Message).count()
        n_stories = db.query(Story).count()
        n_attachments = db.query(Attachment).count()
        n_reactions = db.query(MessageReaction).count()

        print()
        print("=" * 50)
        print(f"  users:        {n_users}")
        print(f"  chats:        {n_chats}")
        print(f"  messages:     {n_msgs}")
        print(f"  attachments:  {n_attachments}")
        print(f"  stories:      {n_stories}")
        print(f"  reactions:    {n_reactions}")
        print()
        print("  login:    alex / demo1234")
        print("  or any:   maria, kenji, sofia, oliver, ananya,")
        print("            dmitry, emma, lukas, yuki, rafael,")
        print("            chen, noah, ivy, liam, zara")
        print("=" * 50)
    finally:
        db.close()


if __name__ == "__main__":
    main()
