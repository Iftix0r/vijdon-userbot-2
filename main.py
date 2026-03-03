"""
Telegram Taxi Bot - Main Application
Admin panel va userbot birgalikda ishga tushirish
"""

import asyncio
import logging
import sys
import re
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from telethon import TelegramClient, events

from config import Config
import database as db
from admin_handlers import router
from ai_classifier import classifier
from utils import setup_logging, format_order_message, truncate_text

# Logging
logger = setup_logging()


class TaxiUserbot:
    """Xabar kuzatish (Telethon) va Bot orqali yuborish"""
    
    def __init__(self, admin_bot=None):
        self.client = None
        self.admin_bot = admin_bot  # aiogram Bot instance
        self.processed_count = 0
        self.forwarded_count = 0
        self.filtered_count = 0
    
    async def start(self):
        """Userbot ishga tushirish"""
        
        try:
            Config.validate_userbot()
        except ValueError as e:
            logger.warning(f"⚠️ Userbot sozlanmagan: {e}")
            return
        
        self.client = TelegramClient(
            Config.SESSION_NAME,
            Config.API_ID,
            Config.API_HASH
        )
        
        logger.info("📱 Userbot ulanmoqda...")
        
        try:
            await self.client.start(phone=Config.PHONE_NUMBER)
            me = await self.client.get_me()
            logger.info(f"✅ Userbot: {me.first_name} (@{me.username or 'yoq'})")
        except Exception as e:
            logger.error(f"❌ Userbot xatosi: {e}")
            return
        
        # Optionally import all joined groups into monitored source groups
        if Config.IMPORT_JOINED_GROUPS:
            try:
                imported = 0
                logger.info("🔎 Importing joined groups into monitored list...")
                async for dialog in self.client.iter_dialogs():
                    try:
                        entity = dialog.entity
                        # Only consider entities that look like chats/channels (have a title)
                        title = getattr(entity, 'title', None)
                        if not title:
                            continue
                        group_id = getattr(entity, 'id', None)
                        if group_id is None:
                            continue
                        # Add to DB (db.add_source_group should handle duplicates)
                        if db.add_source_group(group_id=group_id, title=title, added_by=0):
                            imported += 1
                    except Exception:
                        # skip problematic dialogs
                        continue
                logger.info(f"🔔 Imported {imported} joined groups into monitored list")
            except Exception as e:
                logger.warning(f"Importing joined groups failed: {e}")

        self._setup_handlers()
        await self._check_groups()
        
        logger.info("🟢 Userbot ishlamoqda...")
    
    def _setup_handlers(self):
        """Handler'lar"""
        
        @self.client.on(events.NewMessage())
        async def handle_message(event):
            await self._process_message(event)
    
    async def _check_groups(self):
        """Guruhlarni tekshirish"""
        
        source_groups = db.get_active_group_ids()
        target_group = db.get_target_group()
        
        logger.info(f"📋 Kuzatiladigan guruhlar: {len(source_groups)}")
        
        for group_id in source_groups:
            try:
                entity = await self.client.get_entity(group_id)
                title = getattr(entity, 'title', str(group_id))
                logger.info(f"   ✓ {title}")
                db.add_source_group(group_id, title)
            except Exception as e:
                logger.warning(f"   ✗ {group_id} - {e}")
        
        if target_group:
            try:
                entity = await self.client.get_entity(target_group)
                title = getattr(entity, 'title', str(target_group))
                logger.info(f"📤 Target: {title}")
            except:
                pass
    
    async def _process_message(self, event):
        """Xabarni qayta ishlash"""
        
        try:
            chat_id = event.chat_id
            source_groups = db.get_active_group_ids()
            
            if chat_id not in source_groups:
                return
            
            message = event.message
            
            # Stiker bo'lsa o'tkazib yuborish
            if message.sticker:
                return
            
            # Media bo'lsa va matn yo'q bo'lsa o'tkazib yuborish
            if message.media and not message.text:
                return
            
            text = message.text or message.message or ""
            
            if not text or len(text) < 10:
                return
            
            # 50 belgidan ko'p bo'lsa o'tkazib yuborish (OpenAI tejash)
            if len(text) > 50:
                return
            
            # Faqat emoji bo'lsa o'tkazib yuborish
            import re
            text_without_emoji = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF\s]+', '', text)
            if len(text_without_emoji) < 5:
                return
            
            chat = await event.get_chat()
            sender = await event.get_sender()
            
            # Foydalanuvchi ID olish
            sender_id = sender.id if sender else 0
            
            # Bloklangan foydalanuvchini tekshirish
            if sender_id and db.is_blocked(sender_id):
                logger.debug(f"Bloklangan: {sender_id}")
                return
            
            # Kunlik limit tekshirish (Endi cheklanmagan)
            # if sender_id and not db.check_user_daily_limit(sender_id):
            #     logger.debug(f"Limit tugagan: {sender_id}")
            #     return
            
            # Kalit so'zlar bilan tekshirish
            text_lower = text.lower()
            
            # 1. Haydovchi so'zlari (IGNORE)
            driver_keywords = db.get_keywords('driver')
            for k in driver_keywords:
                if k['word'] in text_lower:
                    return
            
            # 2. Yo'lovchi so'zlari (FORCE ORDER)
            passenger_keywords = db.get_keywords('passenger')
            is_forced_order = False
            for k in passenger_keywords:
                if k['word'] in text_lower:
                    is_forced_order = True
                    break
            
            self.processed_count += 1
            
            chat_title = getattr(chat, 'title', 'Unknown')
            sender_name = self._get_sender_name(sender)
            
            # AI klassifikatsiya yoki Keyword orqali
            if is_forced_order:
                is_ord = True
                order_type = "passenger_order"
                # AI dan faqat ma'lumot olish uchun foydalanamiz, lekin order aniqligi 100%
                _, _, order_data = await classifier.is_order(text)
                if not order_data:
                    order_data = {}
            else:
                is_ord, order_type, order_data = await classifier.is_order(text)
            
            if is_ord:
                # Zakaz sonini oshirish
                if sender_id:
                    db.increment_user_order_count(sender_id)
                await self._forward_order(event, order_data, order_type, chat_title, sender_name)
            else:
                logger.debug(f"Boshqa xabar: {truncate_text(text, 40)}")
            
            db.update_stats(processed=1)
            
        except Exception as e:
            logger.error(f"Xato: {e}")
    
    async def _forward_order(self, event, order_data, order_type, chat_title, sender_name):
        """Buyurtmani yuborish - Bot token orqali inline tugmalar bilan"""
        
        target_groups = db.get_target_groups()
        if not target_groups:
            logger.warning("Target guruhlar sozlanmagan!")
            return
        
        if not self.admin_bot:
            logger.error("Admin bot sozlanmagan!")
            return
        
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            import re
            
            message = event.message
            original_text = message.text or ""
            chat = await event.get_chat()
            sender = await event.get_sender()
            
            # Bot nomi
            bot_name = "Taksichi Brat"
            
            # Foydalanuvchi nomi
            user_name = sender_name
            
            # Xabar matni (qisqa)
            short_text = original_text[:100] if len(original_text) > 100 else original_text
            
            # Vaqt
            from datetime import datetime
            time_str = datetime.now().strftime("%I:%M:%S %p") + " Uzbekistan Standard Time"
            
            # Telefon raqamini topish
            phone = None
            if order_data and order_data.get("phone"):
                phone = order_data["phone"]
            
            # Agar AI topilmagansa, regex orqali izlash
            if not phone:
                # Xabardan telefon izlash - turli formatlarni qo'llab-quvvatlash
                # +998901234567, 998901234567, 901234567, +9 98 90 123 45 67 va h.k.
                phone_patterns = [
                    r'\+998\s*\d{2}\s*\d{3}\s*\d{2}\s*\d{2}',  # +998 90 123 45 67
                    r'\+998\d{9}',  # +998901234567
                    r'998\d{9}',    # 998901234567
                    r'(?<!\d)\d{9}(?!\d)',  # 901234567 (9 raqam)
                ]
                
                for pattern in phone_patterns:
                    phone_match = re.search(pattern, original_text.replace(" ", ""))
                    if phone_match:
                        phone = phone_match.group()
                        break
            
            # Telefon raqamini formatlash
            if phone:
                phone_clean = re.sub(r'[^\d+]', '', phone)
                if not phone_clean.startswith('+'):
                    if phone_clean.startswith('998'):
                        phone_clean = '+' + phone_clean
                    elif len(phone_clean) == 9:
                        phone_clean = '+998' + phone_clean
            else:
                phone_clean = None
            
            # Sender link
            user_link = user_name
            if sender:
                if hasattr(sender, 'username') and sender.username:
                    user_link = f"[{user_name}](https://t.me/{sender.username})"
                elif hasattr(sender, 'id'):
                    user_link = f"[{user_name}](tg://user?id={sender.id})"

            # Xabar formatlash - Rasmda ko'rsatilgan format
            if sender_id:
                user_link = f"tg://user?id={sender_id}"
                formatted = f"👤 [{user_name}]({user_link})"
            else:
                formatted = f"👤 {user_name}"
                
            if sender and hasattr(sender, 'username') and sender.username:
                formatted += f" (@{sender.username})"
            
            formatted += f"\n\n💬 {short_text}\n\n"
            
            if phone_clean:
                formatted += f"📞 {phone_clean}"
            # Raqam yo'q bo'lsa, hech qanday yozuv chiqmaydi
            
            # Barcha target guruhlarga yuborish (Endi akkaunt orqali)
            for target_group in target_groups:
                try:
                    await self.client.send_message(
                        entity=target_group,
                        message=formatted,
                        parse_mode='md'  # Markdown linklar ishlashi uchun
                    )
                except Exception as e:
                    logger.error(f"Guruhga yuborishda xato ({target_group}): {e}")
            
            self.forwarded_count += 1
            db.update_stats(forwarded=1)
            logger.info(f"✅ Akkaunt orqali yuborildi: {truncate_text(original_text, 40)}")
            
        except Exception as e:
            logger.error(f"Yuborishda xato: {e}", exc_info=True)
    
    def _get_sender_name(self, sender):
        if not sender:
            return "Noma'lum"
        
        parts = []
        if hasattr(sender, 'first_name') and sender.first_name:
            parts.append(sender.first_name)
        if hasattr(sender, 'last_name') and sender.last_name:
            parts.append(sender.last_name)
        
        name = " ".join(parts) if parts else "Foydalanuvchi"
        
        if hasattr(sender, 'username') and sender.username:
            name += f" (@{sender.username})"
        
        return name
    
    async def _poll_public_groups(self):
        """Ommaviy guruhlardan xabarlarni polling qilish (a'zo bo'lmasdan)"""
        
        # Oxirgi ko'rilgan xabar ID'lari
        last_message_ids = {}
        
        while True:
            try:
                source_groups = db.get_active_group_ids()
                
                for group_id in source_groups:
                    try:
                        # So'nggi 5 ta xabarni olish
                        messages = await self.client.get_messages(group_id, limit=5)
                        
                        if not messages:
                            continue
                        
                        # Birinchi marta - faqat oxirgi ID'ni saqlash
                        if group_id not in last_message_ids:
                            last_message_ids[group_id] = messages[0].id if messages else 0
                            continue
                        
                        # Yangi xabarlarni qayta ishlash
                        for msg in reversed(messages):
                            if msg.id > last_message_ids.get(group_id, 0):
                                # Fake event yaratish
                                await self._process_polled_message(msg)
                                last_message_ids[group_id] = msg.id
                                
                    except Exception as e:
                        # Xato - ehtimol a'zo emas yoki guruh topilmadi
                        pass
                
                # 10 soniya kutish
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Polling xatosi: {e}")
                await asyncio.sleep(30)
    
    async def _process_polled_message(self, message):
        """Polling orqali olingan xabarni qayta ishlash"""
        
        try:
            text = message.text or message.message or ""
            
            # Stiker/media tekshirish
            if message.sticker or (message.media and not text):
                return
            
            if not text or len(text) < 10 or len(text) > 50:
                return
            
            # Emoji tekshirish
            import re
            text_without_emoji = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF\s]+', '', text)
            if len(text_without_emoji) < 5:
                return
            
            chat = await message.get_chat()
            sender = await message.get_sender()
            
            sender_id = sender.id if sender else 0
            
            # Bloklangan tekshirish
            if sender_id and db.is_blocked(sender_id):
                return
            
            # Limit tekshirish (Endi cheklanmagan)
            # if sender_id and not db.check_user_daily_limit(sender_id):
            #     return
            
            # Kalit so'zlar bilan tekshirish
            text_lower = text.lower()
            
            # 1. Haydovchi so'zlari (IGNORE)
            driver_keywords = db.get_keywords('driver')
            for k in driver_keywords:
                if k['word'] in text_lower:
                    return
            
            # 2. Yo'lovchi so'zlari (FORCE ORDER)
            passenger_keywords = db.get_keywords('passenger')
            is_forced_order = False
            for k in passenger_keywords:
                if k['word'] in text_lower:
                    is_forced_order = True
                    break
            
            chat_title = getattr(chat, 'title', 'Unknown')
            sender_name = self._get_sender_name(sender)
            
            # AI klassifikatsiya
            if is_forced_order:
                is_ord = True
                order_type = "passenger_order"
                _, _, order_data = await classifier.is_order(text)
                if not order_data:
                    order_data = {}
            else:
                is_ord, order_type, order_data = await classifier.is_order(text)
            
            if is_ord:
                if sender_id:
                    db.increment_user_order_count(sender_id)
                await self._forward_polled_order(message, order_data, order_type, chat_title, sender_name)
            
            db.update_stats(processed=1)
            
        except Exception as e:
            logger.error(f"Polled xabar xatosi: {e}")
    
    async def _forward_polled_order(self, message, order_data, order_type, chat_title, sender_name):
        """Polling orqali olingan zakazni yuborish"""
        
        target_groups = db.get_target_groups()
        if not target_groups or not self.admin_bot:
            return
        
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            import re
            
            original_text = message.text or ""
            chat = await message.get_chat()
            sender = await message.get_sender()
            
            user_name = sender_name
            short_text = original_text[:100] if len(original_text) > 100 else original_text
            
            sender_id = sender.id if sender else 0
            if sender_id:
                user_link = f"tg://user?id={sender_id}"
                formatted = f"👤 [{user_name}]({user_link})"
            else:
                formatted = f"👤 {user_name}"
                
            if sender and hasattr(sender, 'username') and sender.username:
                formatted += f" (@{sender.username})"
            
            formatted += f"\n\n💬 {short_text}\n\n"
            
            # Xabardan telefon izlash (polling xabar uchun)
            phone_clean = None
            phone_patterns = [
                r'\+998\s*\d{2}\s*\d{3}\s*\d{2}\s*\d{2}',
                r'\+998\d{9}',
                r'998\d{9}',
                r'(?<!\d)\d{9}(?!\d)',
            ]
            
            import re
            for pattern in phone_patterns:
                phone_match = re.search(pattern, original_text.replace(" ", ""))
                if phone_match:
                    phone_clean = phone_match.group()
                    # format phone
                    phone_clean = re.sub(r'[^\d+]', '', phone_clean)
                    if not phone_clean.startswith('+'):
                        if phone_clean.startswith('998'):
                            phone_clean = '+' + phone_clean
                        elif len(phone_clean) == 9:
                            phone_clean = '+998' + phone_clean
                    break
            
            if not phone_clean and sender and hasattr(sender, 'phone') and sender.phone:
                phone_clean = sender.phone
                if not phone_clean.startswith('+'):
                    phone_clean = '+' + phone_clean

            if phone_clean:
                formatted += f"📞 {phone_clean}"
            # Raqam yo'q bo'lsa, hech qanday yozuv chiqmaydi

            # Barcha target guruhlarga yuborish (Endi akkaunt orqali)
            for target_group in target_groups:
                try:
                    await self.client.send_message(
                        entity=target_group,
                        message=formatted,
                        parse_mode='md'
                    )
                except Exception as e:
                    pass
            
            self.forwarded_count += 1
            db.update_stats(forwarded=1)
            logger.info(f"✅ Polling (Akkaunt): {truncate_text(original_text, 40)}")
            
        except Exception as e:
            logger.error(f"Polling yuborish xatosi: {e}")
    
    async def run_forever(self):
        """Doimiy ishlash"""
        if self.client:
            # Polling o'chirildi - faqat event handler ishlatiladi
            await self.client.run_until_disconnected()


async def run_admin_bot(bot, userbot=None):
    """Admin panel bot"""
    
    dp = Dispatcher(storage=MemoryStorage())
    # Userbot clientni handlerlarga o'tkazish
    dp["userbot"] = userbot
    
    dp.include_router(router)
    
    bot_info = await bot.get_me()
    logger.info(f"✅ Admin bot: @{bot_info.username}")
    
    if Config.SUPER_ADMIN_IDS:
        logger.info(f"👑 Super adminlar: {Config.SUPER_ADMIN_IDS}")
    
    logger.info("🟢 Admin panel ishlamoqda...")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def main():
    """Asosiy funksiya - ikkalasini birga ishga tushirish"""
    
    logger.info("=" * 50)
    logger.info("🚕 Telegram Taxi Bot ishga tushirilmoqda...")
    logger.info("=" * 50)
    
    # Bot yaratish
    bot = None
    try:
        Config.validate_bot()
        bot = Bot(
            token=Config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
    except ValueError as e:
        logger.error(f"❌ Bot sozlanmagan: {e}")
    
    # Userbot (bot instance bilan)
    userbot = TaxiUserbot(admin_bot=bot)
    await userbot.start()
    
    # Ikkala tasklarni parallel ishga tushirish
    tasks = []
    
    if bot:
        tasks.append(asyncio.create_task(run_admin_bot(bot, userbot=userbot)))
    
    # Userbot client mavjud bo'lsa
    if userbot.client:
        tasks.append(asyncio.create_task(userbot.run_forever()))
    
    if not tasks:
        logger.error("❌ Hech qanday xizmat ishga tushmadi!")
        return
    
    logger.info("\n" + "=" * 50)
    logger.info("🟢 Barcha xizmatlar ishlamoqda!")
    logger.info("Admin botga /start yuboring")
    logger.info("To'xtatish: Ctrl+C")
    logger.info("=" * 50 + "\n")
    
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot to'xtatildi")
