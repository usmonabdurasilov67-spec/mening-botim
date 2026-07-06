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
        user_id INTEGER PRIMARY KEY
    )
    """
)
conn.commit()


def add_user(user_id: int) -> None:
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()


def get_all_users() -> list[int]:
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]


def count_users() -> int:
    cursor.execute("SELECT COUNT(*) FROM users")
    return cursor.fetchone()[0]


# ---------- Foydalanuvchi buyruqlari ----------
@dp.message(CommandStart())
async def start_handler(message: Message):
    add_user(message.from_user.id)
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


# ---------- Guruhga yozilgan HAR QANDAY xabarni avtomatik hammaga jo'natish ----------
@dp.message()
async def group_auto_broadcast(message: Message):
    """
    GROUP_ID sifatida ko'rsatilgan guruhga yozilgan har qanday xabar
    (matn, rasm, video, fayl - hammasi) avtomatik ravishda barcha
    ro'yxatdan o'tgan mijozlarga jo'natiladi. Hech qanday buyruq
    yozish shart emas - guruhga yozdingiz, hammaga ketdi.
    """
    if message.chat.id != GROUP_ID:
        return
    if message.text and message.text.startswith("/"):
        return  # buyruqlarni (masalan /stats) e'tiborsiz qoldiramiz

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


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
