from datetime import datetime, timedelta, timezone
import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatPermissions, Message

from config import (
    LOG_CHANNEL_ID,
    MAX_WARNINGS,
    MUTE_DURATION_HOURS,
    VIOLATION_MEDIA,
    VIOLATION_TEXT,
)
from database import add_warning

logger = logging.getLogger(__name__)

# O'zbekiston vaqt mintaqasi (UTC+5)
UZ_TIMEZONE = timezone(timedelta(hours=5))

# Guruh taklif havolalarini qayta-qayta yaratmaslik uchun kesh
_chat_links_cache: dict[int, str] = {}

# Mute holatida barcha yozish huquqlarini o'chirish
MUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)


def _format_user_mention(message: Message) -> str:
    """Foydalanuvchi ismini xavfsiz HTML mention ko'rinishida formatlaydi."""
    if not message.from_user:
        return "Foydalanuvchi"
    full_name = html.escape(message.from_user.full_name or "Foydalanuvchi")
    return f'<a href="tg://user?id={message.from_user.id}">{full_name}</a>'


async def _get_chat_invite_link(bot: Bot, message: Message) -> str | None:
    """Guruhning maxfiy taklif havolasini (https://t.me/+...) oladi."""
    if message.chat.type == "private":
        return None

    chat_id = message.chat.id
    if message.chat.username:
        return f"https://t.me/{message.chat.username}"

    if chat_id in _chat_links_cache:
        return _chat_links_cache[chat_id]

    try:
        invite_link = await bot.export_chat_invite_link(chat_id)
        _chat_links_cache[chat_id] = invite_link
        return invite_link
    except Exception:
        try:
            link_obj = await bot.create_chat_invite_link(
                chat_id=chat_id,
                name="Nazorat Bot Havolasi",
            )
            _chat_links_cache[chat_id] = link_obj.invite_link
            return link_obj.invite_link
        except Exception as exc:
            logger.warning(
                "Guruh taklif havolasini olib bo'lmadi (chat_id=%s): %s",
                chat_id,
                exc,
            )
            return None


async def send_audit_log(
    bot: Bot,
    message: Message,
    violation_type: str,
    penalty_text: str,
) -> None:
    """
    O'chirilayotgan noqonuniy xabar yoki mediani uning muallifi profili,
    guruhi va to'g'ridan-to'g'ri havolalari bilan maxsus nazorat kanaliga yuboradi.
    """
    if not LOG_CHANNEL_ID:
        return

    user = message.from_user
    user_name = html.escape(user.full_name or "Noma'lum") if user else "Foydalanuvchi"
    user_id = user.id if user else "Noma'lum"

    # 1. Foydalanuvchining shaxsiy profiliga to'g'ridan-to'g'ri bosiladigan havola
    if user:
        if user.username:
            user_direct_link = f'<a href="https://t.me/{user.username}">@{user.username}</a> | <a href="tg://user?id={user.id}">Profil ↗️</a> (ID: <code>{user.id}</code>)'
        else:
            user_direct_link = f'<a href="tg://user?id={user.id}">Profilni ochish ↗️</a> (ID: <code>{user.id}</code>)'
    else:
        user_direct_link = "Noma'lum"

    chat_title = html.escape(
        message.chat.title or message.chat.full_name or "Guruh"
    )
    chat_id = message.chat.id
    current_time = datetime.now(UZ_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

    # 2. Guruhga to'g'ridan-to'g'ri o'tuvchi havolalar:
    # A) Guruh ichiga to'g'ridan-to'g'ri o'tuvchi havola (Telegram t.me/c linki):
    clean_chat_id = str(chat_id).replace("-100", "").replace("-", "")
    if message.chat.username:
        group_direct_url = f"https://t.me/{message.chat.username}"
    elif message.chat.type != "private":
        group_direct_url = f"https://t.me/c/{clean_chat_id}/{message.message_id}"
    else:
        group_direct_url = None

    # B) Guruhga a'zo bo'lish uchun taklif havolasi (Invite Link):
    invite_url = await _get_chat_invite_link(bot, message)

    v_title = (
        "🔞 18+ Media (Topless / Pornografiya)"
        if violation_type == VIOLATION_MEDIA
        else "🤬 So'kinish (Matn)"
    )

    group_section = f"👥 <b>Guruh:</b> <b>{chat_title}</b> (ID: <code>{chat_id}</code>)\n"
    if group_direct_url:
        group_section += f"👉 <b>Guruhni ochish:</b> <a href=\"{group_direct_url}\">{group_direct_url}</a>\n"
    if invite_url and invite_url != group_direct_url:
        group_section += f"🔗 <b>Taklif havolasi (Invite):</b> <a href=\"{invite_url}\">{invite_url}</a>\n"

    report_text = (
        f"🚨 <b>NOQONUNIY KONTENT QAYD ETILDI</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> <a href=\"tg://user?id={user_id}\">{user_name}</a>\n"
        f"🔗 <b>Foydalanuvchi havolasi:</b> {user_direct_link}\n\n"
        f"{group_section}\n"
        f"⏰ <b>Vaqt:</b> {current_time} (Toshkent)\n"
        f"⚠️ <b>Qoidabuzarlik:</b> {v_title}\n"
        f"⚖️ <b>Jazo:</b> {penalty_text}"
    )

    has_media = bool(
        message.photo
        or message.video
        or message.animation
        or message.sticker
        or message.video_note
        or message.document
    )

    try:
        # 1. Avval asosiy batafsil ma'lumot matnini kanalga alohida xabar qilib yuboramiz
        report_msg = await bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=report_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        # 2. Keyin o'sha noqonuniy fayl yoki matnning o'zini hisobotga javob (reply) qilib ulaymiz
        if has_media:
            try:
                await message.copy_to(
                    chat_id=LOG_CHANNEL_ID,
                    reply_to_message_id=report_msg.message_id,
                )
            except Exception:
                await message.forward(
                    chat_id=LOG_CHANNEL_ID,
                )
        else:
            text_content = html.escape(message.text or message.caption or "")
            if text_content:
                await bot.send_message(
                    chat_id=LOG_CHANNEL_ID,
                    text=f"💬 <b>Yozilgan so'z:</b>\n<blockquote>{text_content}</blockquote>",
                    parse_mode="HTML",
                    reply_to_message_id=report_msg.message_id,
                )

        logger.info(
            "Audit log kanalga to'liq yuborildi: chat_id=%s, user_id=%s",
            chat_id,
            user_id,
        )
    except Exception as exc:
        logger.warning(
            "Audit log kanalga yuborilmadi (LOG_CHANNEL_ID=%s): %s",
            LOG_CHANNEL_ID,
            exc,
        )


async def delete_offending_message(message: Message) -> bool:
    """Qoidabuzarlik xabarini darhol o'chiradi."""
    try:
        await message.delete()
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.warning(
            "Xabarni o'chirib bo'lmadi (chat_id=%s, msg_id=%s): %s",
            message.chat.id,
            message.message_id,
            exc,
        )
        return False


async def _mute_user_24h(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Foydalanuvchini 24 soatga guruhda yozishdan cheklaydi (Mute)."""
    until_date = datetime.now(timezone.utc) + timedelta(hours=MUTE_DURATION_HOURS)
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=MUTE_PERMISSIONS,
            until_date=until_date,
        )
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.warning(
            "Foydalanuvchini Mute qilib bo'lmadi (chat_id=%s, user_id=%s): %s",
            chat_id,
            user_id,
            exc,
        )
        return False


async def _ban_or_forever_spam_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Foydalanuvchini guruhdan butunlayga chetlatadi (Ban / umrbod spam-blok).
    Agar ban_chat_member ruxsati cheklangan bo'lsa, umrbod mute qo'llaydi.
    """
    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id, revoke_messages=False)
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.warning(
            "Foydalanuvchini Ban qilib bo'lmadi (chat_id=%s, user_id=%s): %s",
            chat_id,
            user_id,
            exc,
        )
        try:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=MUTE_PERMISSIONS,
            )
            return True
        except (TelegramBadRequest, TelegramForbiddenError):
            return False


async def handle_violation(message: Message, violation_type: str) -> None:
    """
    Aniqlangan qoidabuzarlik bo'yicha:
    1. Xabar, foydalanuvchi profili, guruh havolasi va dalilni nazorat kanaliga (Audit Log) yuboradi;
    2. Xabarni guruhdan o'chiradi;
    3. Jazo zanjirini qo'llaydi va guruhga ogohlantirish beradi.
    """
    if not message.from_user:
        await delete_offending_message(message)
        return

    bot: Bot = message.bot  # type: ignore[assignment]
    chat_id = message.chat.id
    user_id = message.from_user.id
    mention = _format_user_mention(message)
    is_group = message.chat.type != "private"

    # 1. 18+ Media qoidabuzarligi -> Darhol Ban
    if violation_type == VIOLATION_MEDIA:
        penalty_text = "Ogohlantirishsiz Guruhdan Ban (chetlatish)"
        # Avval kanalga batafsil ma'lumot va dalilni yuboramiz
        await send_audit_log(bot, message, violation_type, penalty_text)
        # Guruhdan xabarni o'chiramiz
        await delete_offending_message(message)

        banned = await _ban_or_forever_spam_user(bot, chat_id, user_id) if is_group else False
        note = ""
        if is_group and not banned:
            note = "\n<i>(Eslatma: Foydalanuvchi guruh egasi/admini bo'lgani uchun Telegram uni bloklashga ruxsat bermadi, lekin 18+ media o'chirildi)</i>"
        await message.answer(
            f"🚫 {mention} taqiqlangan 18+ (NSFW) media yuborgani sababli "
            f"xabar o'chirildi va foydalanuvchi guruhdan chetlatildi (Ban)!{note}",
            parse_mode="HTML",
        )
        return

    # 2. Matn (so'kinish) qoidabuzarligi -> Warn zanjiri
    if violation_type == VIOLATION_TEXT:
        warn_count = await add_warning(user_id=user_id, chat_id=chat_id)

        if warn_count < MAX_WARNINGS:
            penalty_text = f"Ogohlantirish ({warn_count}/{MAX_WARNINGS})"
            await send_audit_log(bot, message, violation_type, penalty_text)
            await delete_offending_message(message)

            await message.answer(
                f"⚠️ {mention}, guruhda haqoratli va so'kinish so'zlarini ishlatish taqiqlangan!\n"
                f"Ogohlantirish: <b>{warn_count}/{MAX_WARNINGS}</b>",
                parse_mode="HTML",
            )
        elif warn_count == MAX_WARNINGS:
            penalty_text = f"{MAX_WARNINGS}/{MAX_WARNINGS} ogohlantirish -> {MUTE_DURATION_HOURS} soatga Mute"
            await send_audit_log(bot, message, violation_type, penalty_text)
            await delete_offending_message(message)

            muted = await _mute_user_24h(bot, chat_id, user_id) if is_group else False
            note = ""
            if is_group and not muted:
                note = "\n<i>(Eslatma: Foydalanuvchi guruh egasi/admini bo'lgani uchun Telegram cheklov qo'yishga ruxsat bermadi, lekin xabar o'chirildi)</i>"
            await message.answer(
                f"🔇 {mention} <b>{MAX_WARNINGS}/{MAX_WARNINGS}</b> ogohlantirish oldi va "
                f"<b>{MUTE_DURATION_HOURS} soatga</b> yozishdan cheklandi (Mute)!\n"
                f"❗️ Keyingi qoidabuzarlikda guruhdan butunlayga bloklanasiz.{note}",
                parse_mode="HTML",
            )
        else:
            penalty_text = "Qayta takrorlangan so'kinish -> Guruhda butunlayga Ban / Spam blok"
            await send_audit_log(bot, message, violation_type, penalty_text)
            await delete_offending_message(message)

            banned = await _ban_or_forever_spam_user(bot, chat_id, user_id) if is_group else False
            note = ""
            if is_group and not banned:
                note = "\n<i>(Eslatma: Foydalanuvchi guruh egasi/admini bo'lgani uchun Telegram uni bloklashga ruxsat bermadi, lekin xabar o'chirildi)</i>"
            await message.answer(
                f"🚫 {mention} 24 soatlik cheklovdan keyin ham qoidabuzarlikni takrorlagani sababli "
                f"guruhda butunlayga bloklandi (Spam/Ban)!{note}",
                parse_mode="HTML",
            )
