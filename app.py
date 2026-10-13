import asyncio
import logging
import os
import sys
import threading

import gradio as gr
from aiogram import Bot, Dispatcher

from bot import on_startup, router
from config import BOT_TOKEN, LOG_CHANNEL_ID
from filters.text_filter import BAD_WORDS_SET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("huggingface_gradio_app")


def run_telegram_bot_loop() -> None:
    """Telegram bot dispatcherini alohida fonda (thread) ishga tushiradi."""
    token = BOT_TOKEN or os.getenv("BOT_TOKEN", "")
    if not token or "your_telegram_bot_token_here" in token:
        logger.error(
            "BOT_TOKEN topilmadi! Iltimos, Hugging Face Settings -> Secrets bo'limida BOT_TOKEN ni kiriting."
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


# 2. Hugging Face 24/7 yashil "Running" holatida ushlab turishi uchun bepul Gradio veb-interfeysi
with gr.Blocks(title="Telegram Moderatsiya Boti") as demo:
    gr.Markdown(
        """
        # 🛡 Telegram Moderatsiya Boti (24/7 Bepul Serverda)
        
        ### ✅ Holat: Faol ishlamoqda
        - **Neyrotarmoq (ONNX):** NudeNet + NSFWJS (CPU tahlil)
        - **Matn filtri:** O'zbek va rus tillari (4 900+ so'z shakllari)
        - **Nazorat kanali (Audit Log):** Ulangan
        
        *Ushbu bot Hugging Face Spaces bepul serverida 24 soat uzluksiz ishlaydi.*
        """
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
