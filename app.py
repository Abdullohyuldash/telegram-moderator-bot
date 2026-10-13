import asyncio
import logging
import os
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher

from bot import on_startup, router
from config import BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("render_app")


async def handle_health_check(request: web.Request) -> web.Response:
    """Render.com uchun 200 OK qaytaruvchi yengil status sahifasi."""
    html_content = """
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <title>Telegram Moderatsiya Boti</title>
        <style>
            body { font-family: sans-serif; background: #0f172a; color: white; text-align: center; padding: 60px 20px; }
            .card { max-width: 500px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 12px; border: 1px solid #334155; }
            .badge { background: #10b981; color: white; padding: 6px 14px; border-radius: 20px; font-weight: bold; display: inline-block; }
            h1 { font-size: 22px; margin: 15px 0 10px; }
            p { color: #94a3b8; font-size: 15px; }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="badge">● 24/7 ISHLAMOQDA</div>
            <h1>🛡 Telegram Moderatsiya Boti Faol</h1>
            <p>Neyrotarmoq (ONNX) va so'kinish filtri serverda uzluksiz xizmat ko'rsatmoqda.</p>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html")


async def main() -> None:
    token = BOT_TOKEN or os.getenv("BOT_TOKEN", "")
    if not token or "your_telegram_bot_token_here" in token:
        logger.error(
            "BOT_TOKEN topilmadi! Iltimos, Render Environment bo'limida BOT_TOKEN ni kiriting."
        )
        sys.exit(1)

    # 1. SQLite baza va ONNX neyrotarmoq modellarini yuklash
    await on_startup()

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)

    # 2. Render talab qiladigan aiohttp veb-serverini bir vaqtda ishga tushirish (0.0.0.0:10000)
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/health", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Veb-server 0.0.0.0:%d portida muvaffaqiyatli ochildi.", port)

    # 3. Telegram Pollingni asosiy oqimda to'liq xavfsiz yurgizish
    logger.info("Telegram Moderatsiya Boti 24/7 ishga tushdi (Polling)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
