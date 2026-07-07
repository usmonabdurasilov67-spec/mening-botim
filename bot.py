import asyncio
import logging
import sqlite3

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

# ============ SOZLAMALAR ============
API_TOKEN = "8976497371:AAH3d94T7saNas48OFFSUlvg_uzmNIDXHiw"
ADMIN_ID = 8967541811                  # O'zingizning Telegram ID raqamingiz (masalan @userinfobot orqali oling)
GROUP_ID = -1003916849544             # Reklama guruhingizning ID raqami (pastdagi qo'llanmaga qarang)
# =====================================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ---------- Ma'lumotlar bazasi (SQLite) ----------
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        full_name TEXT,
        username TEXT,
        joined_at TEXT
    )
    """
)
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS forward_map (
        admin_msg_id INTEGER PRIMARY KEY,
        user_id INTEGER
    )
    """
)
conn.commit()


def add_user(user_id: int, full_name: str = "", username: str = "") -> None:
    cursor.execute(
        """
        INSERT INTO users (user_id, full_name, username, joined_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
            full_name = excluded.full_name,
            username = excluded.username
        """,
        (user_id, full_name, username),
    )
    conn.commit()


def get_all_users() -> list[int]:
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]


def get_all_users_info() -> list[tuple]:
    cursor.execute("SELECT user_id, full_name, username, joined_at FROM users ORDER BY joined_at DESC")
    return cursor.fetchall()


def count_users() -> int:
    cursor.execute("SELECT COUNT(*) FROM users")
    return cursor.fetchone()[0]


def save_forward(admin_msg_id: int, user_id: int) -> None:
    cursor.execute(
        "INSERT OR REPLACE INTO forward_map (admin_msg_id, user_id) VALUES (?, ?)",
        (admin_msg_id, user_id),
    )
    conn.commit()


def get_client_by_forward(admin_msg_id: int) -> int | None:
    cursor.execute("SELECT user_id FROM forward_map WHERE admin_msg_id = ?", (admin_msg_id,))
    row = cursor.fetchone()
    return row[0] if row else None


# ---------- Foydalanuvchi buyruqlari ----------
@dp.message(CommandStart())
async def start_handler(message: Message):
    add_user(
        message.from_user.id,
        message.from_user.full_name or "",
        message.from_user.username or "",
    )
    await message.answer(
        "Xush kelibsiz! ✅\n"
        "Siz ro'yxatdan muvaffaqiyatli o'tdingiz.\n"
        "Endi barcha yangiliklar va reklamalar shu yerga keladi."
    )


# ---------- Admin buyruqlari ----------
@dp.message(Command("stats"))
async def stats_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(f"📊 Ro'yxatdan o'tgan foydalanuvchilar: {count_users()}")


@dp.message(Command("users"))
async def users_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = get_all_users_info()
    if not users:
        await message.answer("Hozircha hech kim ro'yxatdan o'tmagan.")
        return

    lines = [f"👥 Jami: {len(users)} kishi\n"]
    for user_id, full_name, username, joined_at in users:
        name = full_name or "Ism yo'q"
        uname = f"@{username}" if username else "username yo'q"
        lines.append(f"• {name} ({uname}) — ID: {user_id}")

    # Telegram xabar uzunligi cheklangani uchun 4000 belgidan bo'lib yuboramiz
    text = "\n".join(lines)
    for i in range(0, len(text), 4000):
        await message.answer(text[i:i + 4000])


@dp.message(Command("reklama"))
async def broadcast_handler(message: Message):
    """
    Ishlatish:
    1) /reklama Matn shu yerda  -> oddiy matnli xabar barchaga yuboriladi
    2) Rasm/video/faylga JAVOB tariqasida /reklama yozsangiz
       -> o'sha xabar (rasm bilan birga) barchaga yuboriladi
    """
    if message.from_user.id != ADMIN_ID:
        return

    users = get_all_users()
    if not users:
        await message.answer("Hozircha ro'yxatdan o'tgan foydalanuvchi yo'q.")
        return

    await message.answer(f"⏳ Yuborish boshlandi... Jami: {len(users)} kishi")

    success, failed = 0, 0

    # Agar biror xabarga (rasm/video/fayl) javob tariqasida yuborilgan bo'lsa - o'shani ko'chirib yuboramiz
    source_message = message.reply_to_message
    text_after_command = message.text.replace("/reklama", "", 1).strip()

    for user_id in users:
        try:
            if source_message:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=source_message.message_id,
                )
            elif text_after_command:
                await bot.send_message(user_id, text_after_command)
            else:
                await message.answer(
                    "Reklama matnini shu formatda yuboring:\n"
                    "/reklama Sizning matningiz\n\n"
                    "yoki rasm/video/faylga javob tariqasida /reklama deb yozing."
                )
                return
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Telegram flood-limitiga tushmaslik uchun kichik pauza

    await message.answer(f"✅ Yuborildi: {success}\n❌ Yuborilmadi: {failed}")


# ---------- Uchta holatni boshqaruvchi umumiy handler ----------
@dp.message()
async def message_router(message: Message):
    # 1) Reklama guruhiga yozilgan HAR QANDAY xabar - avtomatik hammaga jo'natiladi
    if message.chat.id == GROUP_ID:
        if message.text and message.text.startswith("/"):
            return  # buyruqlarni e'tiborsiz qoldiramiz
        users = get_all_users()
        for user_id in users:
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
            except Exception:
                pass
            await asyncio.sleep(0.05)
        return

    # 2) Admin biror mijoz xabariga JAVOB (reply) yozsa - javob o'sha mijozga ketadi
    if message.from_user.id == ADMIN_ID and message.reply_to_message:
        client_id = get_client_by_forward(message.reply_to_message.message_id)
        if client_id:
            try:
                await bot.copy_message(
                    chat_id=client_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
                await message.reply("✅ Javobingiz mijozga yuborildi")
            except Exception:
                await message.reply(
                    "❌ Yuborib bo'lmadi (mijoz botni bloklagan bo'lishi mumkin)"
                )
            return

    # 3) Oddiy mijozdan (admin bo'lmagan, shaxsiy chatdan) kelgan xabar - adminga yuboriladi
    if message.from_user.id != ADMIN_ID and message.chat.type == "private":
        add_user(
            message.from_user.id,
            message.from_user.full_name or "",
            message.from_user.username or "",
        )
        forwarded = await bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        save_forward(forwarded.message_id, message.from_user.id)
        info_msg = await bot.send_message(
            ADMIN_ID,
            f"👆 Yuqoridagi xabar shu mijozdan:\n"
            f"{message.from_user.full_name} (ID: {message.from_user.id})\n\n"
            f"Javob berish uchun shu xabarga (yoki yuqoridagisiga) JAVOB (reply) qilib yozing.",
        )
        save_forward(info_msg.message_id, message.from_user.id)
        return


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
