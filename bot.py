import asyncio
import io
import logging
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from action_handler import handle_violation
from config import BOT_TOKEN, VIOLATION_MEDIA, VIOLATION_TEXT
from database import init_db, reset_warnings
try:
    from filters.media_filter import check_media, ensure_model_exists, get_onnx_session
    from filters.text_filter import (
        BAD_WORDS_SET,
        add_custom_bad_words,
        check_text,
        reload_bad_words,
    )
except ImportError:
    from media_filter import check_media, ensure_model_exists, get_onnx_session
    from text_filter import (
        BAD_WORDS_SET,
        add_custom_bad_words,
        check_text,
        reload_bad_words,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("moderator_bot")

router = Router()


async def extract_media_bytes_to_ram(message: Message) -> bytes | None:
    """
    TZ 4.2-bandiga muvofiq:
    - Video / GIF (animation) / VideoNote / Document: To'liq fayl yuklab olinmaydi,
      faqat Telegram taqdim etgan kichik muqova rasmi (thumbnail) RAMga olinadi.
    - Rasm (photo): Ko'krak uchlari va mayda detallar xira bo'lib qolmasligi uchun
      tiniq ( ~600-800px ) kadr xotiraga (RAM) yuklanadi.
    - Stiker (sticker): Statik stikerning o'zi yoki animatsion/video stikerning thumbnail'i RAMga yuklanadi.
    Diskka hech qanday fayl yozilmaydi.
    """
    file_id: str | None = None

    if message.photo:
        # Kichik 90px thumbnail emas, aniq ko'rinadigan kadrni tanlash
        target_photo = message.photo[-1]
        for p in message.photo:
            if p.width >= 320 and p.height >= 320:
                target_photo = p
                if p.width >= 600 or p.height >= 600:
                    break
        file_id = target_photo.file_id
    elif message.video:
        if message.video.thumbnail:
            file_id = message.video.thumbnail.file_id
    elif message.animation:
        if message.animation.thumbnail:
            file_id = message.animation.thumbnail.file_id
    elif message.sticker:
        if message.sticker.is_animated or message.sticker.is_video:
            if message.sticker.thumbnail:
                file_id = message.sticker.thumbnail.file_id
        else:
            file_id = message.sticker.file_id
    elif message.video_note:
        if message.video_note.thumbnail:
            file_id = message.video_note.thumbnail.file_id
    elif message.document:
        if message.document.thumbnail:
            file_id = message.document.thumbnail.file_id

    if not file_id or not message.bot:
        return None

    try:
        buffer = io.BytesIO()
        await message.bot.download(file=file_id, destination=buffer)
        return buffer.getvalue()
    except Exception as exc:
        logger.warning("Media faylni RAMga yuklashda xatolik (file_id=%s): %s", file_id, exc)
        return None


@router.message(CommandStart(), F.chat.type == "private")
@router.message(Command("help"), F.chat.type == "private")
async def cmd_start_private(message: Message) -> None:
    """Shaxsiy yozishmada bot haqida ma'lumot beradi."""
    await message.answer(
        "🛡 <b>Telegram Moderatsiya Boti</b>\n\n"
        f"📚 Bazadagi faol taqiqlangan so'z shakllari soni: <b>{len(BAD_WORDS_SET)} ta</b>\n\n"
        "Men guruhlarda va test rejimida quyidagi qoidabuzarliklarni avtomatik aniqlab chora ko'raman:\n"
        "1️⃣ <b>O'zbek va rus tillaridagi (lotin/kirill/translit) so'kinishlar:</b>\n"
        "   • 1-marta: Xabar o'chiriladi + Ogohlantirish (1/3)\n"
        "   • 2-marta: Xabar o'chiriladi + Ogohlantirish (2/3)\n"
        "   • 3-marta: Xabar o'chiriladi + 24 soatga Mute\n"
        "   • 4-marta (qayta takrorlansa): Guruhdan butunlayga Ban (Spam)\n\n"
        "2️⃣ <b>18+ Pornografik, Topless (ko'krak uchlari ochiq) va Hentai media fayllar:</b>\n"
        "   • Xabar darhol o'chiriladi + Foydalanuvchi ogohlantirishsiz Ban qilinadi.\n\n"
        "🛠 <b>Maxsus buyruqlar:</b>\n"
        "• <code>/addword so'z1 so'z2</code> — Ro'yxatga yangi taqiqlangan so'z qo'shish\n"
        "• <code>/words</code> — Lug'atdagi jami so'zlar sonini ko'rish va yangilash\n"
        "• <code>/reset</code> — Test uchun ogohlantirishlar hisobini 0/3 ga qaytarish",
        parse_mode="HTML",
    )


@router.message(Command("addword"))
async def cmd_add_word(message: Message) -> None:
    """Yangi taqiqlangan so'zlarni Telegram orqali custom_bad_words.txt ga qo'shish."""
    if not message.text:
        return
    parts = message.text.split()[1:]
    if not parts:
        await message.answer(
            "ℹ️ So'z qo'shish uchun buyruqdan keyin so'zni yozing.\n"
            "Masalan: <code>/addword yomonsoz1 yomonsoz2</code>",
            parse_mode="HTML",
        )
        return

    added = add_custom_bad_words(parts)
    if added:
        await message.answer(
            f"✅ Qo'shildi: <b>{', '.join(added)}</b> (+ barcha qo'shimcha shakllari bilan).\n"
            f"📚 Jami bazadagi so'z shakllari: <b>{len(BAD_WORDS_SET)} ta</b>",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"ℹ️ Ushbu so'z(lar) allaqachon ro'yxatda mavjud.\n"
            f"📚 Jami bazadagi so'z shakllari: <b>{len(BAD_WORDS_SET)} ta</b>",
            parse_mode="HTML",
        )


@router.message(Command("words"))
async def cmd_words_count(message: Message) -> None:
    """custom_bad_words.txt faylini qayta o'qib, jami so'zlar sonini ko'rsatadi."""
    total = reload_bad_words()
    await message.answer(
        f"📚 Lug'at yangilandi! Hozirda <b>{total} ta</b> so'z va qo'shimcha shakllari faol.",
        parse_mode="HTML",
    )


@router.message(Command("reset"))
async def cmd_reset_warnings(message: Message) -> None:
    """Test vaqtida ogohlantirishlar hisobini 0 ga tushirish buyrug'i."""
    if message.from_user:
        await reset_warnings(message.from_user.id, message.chat.id)
        await message.answer("🔄 Sizning ogohlantirishlar hisobingiz 0/3 ga tiklandi.")


@router.message(F.chat.type.in_({"group", "supergroup", "private"}))
@router.edited_message(F.chat.type.in_({"group", "supergroup", "private"}))
async def moderate_message(message: Message) -> None:
    """
    Guruhdagi hamda shaxsiy lichkadagi (test uchun) har bir yangi va tahrirlangan xabarni
    media va matn qoidabuzarligiga tekshiradi.
    """
    # 1. Media tekshiruvi (agar xabarda rasm, video, GIF, stiker bo'lsa)
    media_bytes = await extract_media_bytes_to_ram(message)
    if media_bytes:
        media_result = await check_media(media_bytes)
        if media_result == VIOLATION_MEDIA:
            await handle_violation(message, VIOLATION_MEDIA)
            return

    # 2. Matn tekshiruvi (message.text yoki media ostidagi message.caption)
    text_content = message.text or message.caption
    if text_content:
        text_result = check_text(text_content)
        if text_result == VIOLATION_TEXT:
            await handle_violation(message, VIOLATION_TEXT)
            return

    # 3. Agar shaxsiy lichkada (test rejimida) yuborilgan xabar toza bo'lsa, foydalanuvchiga bildirish
    if message.chat.type == "private":
        await message.answer("✅ Tekshiruv natijasi: Xabar toza (qoidabuzarlik topilmadi).")


async def on_startup() -> None:
    """Bot ishga tushishidan oldin SQLite bazani va ONNX modelni tayyorlaydi."""
    logger.info("SQLite ma'lumotlar bazasi tekshirilmoqda...")
    await init_db()

    logger.info("ONNX NSFW modeli tekshirilmoqda va CPU xotirasiga yuklanmoqda...")
    await asyncio.to_thread(ensure_model_exists)
    await asyncio.to_thread(get_onnx_session)
    logger.info(
        "Barcha modullar tayyor! Faol taqiqlangan so'z shakllari: %d ta",
        len(BAD_WORDS_SET),
    )


async def main() -> None:
    if not BOT_TOKEN or "your_telegram_bot_token_here" in BOT_TOKEN:
        logger.error(
            "BOT_TOKEN topilmadi! Iltimos, .env fayliga haqiqiy BOT_TOKEN qiymatini kiriting."
        )
        sys.exit(1)

    await on_startup()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Telegram Moderatsiya Boti ishga tushdi (Polling)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
