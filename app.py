import asyncio
import logging
import os
import sys
import threading

import gradio as gr
from aiogram import Bot, Dispatcher

from bot import on_startup, router
from config import BOT_TOKEN, LOG_CHANNEL_ID

try:
    from filters.text_filter import BAD_WORDS_SET
except ImportError:
    from text_filter import BAD_WORDS_SET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("render_app")


def run_telegram_bot_loop() -> None:
    """Telegram bot dispatcherini alohida fonda (thread) ishga tushiradi."""
    token = BOT_TOKEN or os.getenv("BOT_TOKEN", "")
    if not token or "your_telegram_bot_token_here" in token:
        logger.error(
            "BOT_TOKEN topilmadi! Iltimos, Render Environment bo'limida BOT_TOKEN ni kiriting."
        )
        return

    async def _async_main() -> None:
        try:
            logger.info("Bot initsializatsiyasi boshlanmoqda...")
            await on_startup()

            bot = Bot(token=token)
            dp = Dispatcher()
            dp.include_router(router)

            logger.info("Telegram Moderatsiya Boti 24/7 ishga tushdi (Polling)...")
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        except Exception as exc:
            logger.error("Bot ishida kutilmagan xatolik: %s", exc, exc_info=True)

    asyncio.run(_async_main())


# 1. Telegram botni fonga olib, uzluksiz ishga tushiramiz
bot_thread = threading.Thread(target=run_telegram_bot_loop, daemon=True)
bot_thread.start()


# 2. Render 24/7 "Live" holatida ushlab turishi uchun Gradio veb-interfeysi
with gr.Blocks(title="Telegram Moderatsiya Boti") as demo:
    gr.Markdown(
        """
        # 🛡 Telegram Moderatsiya Boti (24/7 Bepul Serverda)
        
        ### ✅ Holat: Faol ishlamoqda
        - **Neyrotarmoq (ONNX):** NudeNet + NSFWJS (CPU tahlil)
        - **Matn filtri:** O'zbek va rus tillari (4 900+ so'z shakllari)
        - **Nazorat kanali (Audit Log):** Ulangan
        
        *Ushbu bot Render.com bepul serverida 24 soat uzluksiz ishlaydi.*
        """
    )


if __name__ == "__main__":
    # Render o'zining PORT (10000) o'zgaruvchisini taqdim etadi
    port = int(os.getenv("PORT", 10000))
    logger.info("Veb-server porti: %d", port)
    demo.launch(server_name="0.0.0.0", server_port=port)
