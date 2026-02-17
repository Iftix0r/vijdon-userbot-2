"""
Telegram Taxi Bot - Admin Panel (Aiogram)
Bot token orqali ishlaydigan admin panel
"""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from admin_handlers import router
from utils import setup_logging

# Logging
logger = setup_logging()


async def main():
    """Asosiy funksiya"""
    
    logger.info("=" * 50)
    logger.info("🤖 Admin Panel Bot ishga tushirilmoqda...")
    logger.info("=" * 50)
    
    # Sozlamalarni tekshirish
    try:
        Config.validate_bot()
        logger.info("✅ Sozlamalar to'g'ri")
    except ValueError as e:
        logger.error(f"❌ Sozlamalar xatosi:\n{e}")
        sys.exit(1)
    
    # Bot yaratish
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    
    # Dispatcher
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    # Bot ma'lumotlari
    bot_info = await bot.get_me()
    logger.info(f"✅ Bot: @{bot_info.username}")
    
    if Config.SUPER_ADMIN_IDS:
        logger.info(f"👑 Super adminlar: {Config.SUPER_ADMIN_IDS}")
    else:
        logger.warning("⚠️ SUPER_ADMIN_IDS sozlanmagan!")
    
    logger.info("\n" + "=" * 50)
    logger.info("🟢 Admin panel ishlamoqda...")
    logger.info("Botga /start buyrug'ini yuboring")
    logger.info("=" * 50 + "\n")
    
    # Polling boshlash
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Admin panel to'xtatildi")
