"""
Telegram Taxi Userbot - Xabar kuzatish
Telethon orqali guruhlardan xabarlarni kuzatish
Aiogram orqali zakazlarni yuborish
"""

import asyncio
import logging
import sys
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from aiogram import Bot
from aiogram.enums import ParseMode

from config import Config
import database as db
from ai_classifier import classifier
from utils import setup_logging, format_order_message, truncate_text

# Logging
logger = setup_logging()


class TaxiUserbot:
    """Taxi userbot - xabar kuzatish va yuborish"""
    
    def __init__(self):
        self.client = None
        self.bot = None  # Aiogram bot
        self.processed_count = 0
        self.forwarded_count = 0
        self.filtered_count = 0
        self.user_last_order = {}  # User ID -> timestamp (flood oldini olish)
    
    async def notify_admins(self, message: str):
        """Adminlarga xabar yuborish"""
        try:
            admins = db.get_all_admins()
            for admin in admins:
                try:
                    await self.bot.send_message(admin['user_id'], message)
                except Exception as e:
                    logger.debug(f"Admin {admin['user_id']}ga xabar yuborib bo'lmadi: {e}")
        except Exception as e:
            logger.error(f"Adminlarga xabar yuborishda xato: {e}")
    
    async def start(self):
        """Userbot'ni ishga tushirish"""
        
        logger.info("=" * 50)
        logger.info("🚕 Taxi Userbot ishga tushirilmoqda...")
        logger.info("=" * 50)
        
        # Sozlamalarni tekshirish
        try:
            Config.validate_userbot()
            logger.info("✅ Sozlamalar to'g'ri")
        except ValueError as e:
            logger.error(f"❌ Sozlamalar xatosi:\n{e}")
            sys.exit(1)
        
        # Bot yaratish (zakazlarni yuborish uchun)
        self.bot = Bot(token=Config.BOT_TOKEN)
        logger.info("✅ Bot yaratildi (zakazlarni yuborish uchun)")
        
        # Client yaratish (xabarlarni kuzatish uchun)
        self.client = TelegramClient(
            Config.SESSION_NAME,
            Config.API_ID,
            Config.API_HASH
        )
        
        logger.info("📱 Telegram'ga ulanilmoqda...")
        
        try:
            await self.client.start(phone=Config.PHONE_NUMBER)
            me = await self.client.get_me()
            logger.info(f"✅ Kirish: {me.first_name} (@{me.username or 'yoq'})")
            
        except SessionPasswordNeededError:
            logger.error("❌ 2FA yoqilgan. Parolni kiriting.")
            password = input("2FA parol: ")
            await self.client.sign_in(password=password)
        
        # Handler'larni sozlash
        self._setup_handlers()
        
        # Guruhlarni tekshirish
        await self._check_groups()
        
        logger.info("\n" + "=" * 50)
        logger.info("🟢 Userbot ishlamoqda...")
        logger.info("=" * 50 + "\n")
        
        # Ishga tushirish
        await self.client.run_until_disconnected()
    
    def _setup_handlers(self):
        """Handler'larni sozlash"""
        
        @self.client.on(events.NewMessage())
        async def handle_message(event):
            """Yangi xabar"""
            await self._process_message(event)
        
        logger.info("✅ Handler'lar sozlandi")
    
    async def _check_groups(self):
        """Guruhlarni tekshirish"""
        
        # Agar IMPORT_JOINED_GROUPS yoqilgan bo'lsa, barcha guruhlarni import qilish
        if Config.IMPORT_JOINED_GROUPS:
            logger.info("\n📥 Akauntdagi barcha guruhlar import qilinmoqda...")
            await self._import_all_groups()
        
        source_groups = db.get_active_group_ids()
        target_groups = db.get_target_groups()
        monitored_groups = db.get_monitored_groups()
        
        logger.info(f"\n📋 Kuzatiladigan guruhlar (source): {len(source_groups)}")
        
        for group_id in source_groups:
            try:
                entity = await self.client.get_entity(group_id)
                title = getattr(entity, 'title', str(group_id))
                logger.info(f"   ✓ {title}")
                # DB ni yangilash
                db.add_source_group(group_id, title)
            except Exception as e:
                logger.warning(f"   ✗ {group_id} - {e}")
        
        logger.info(f"\n📤 Target guruhlar (buyurtmalar): {len(target_groups)}")
        for target_group in target_groups:
            try:
                entity = await self.client.get_entity(target_group)
                title = getattr(entity, 'title', str(target_group))
                logger.info(f"   ✓ {title}")
            except Exception as e:
                logger.error(f"   ✗ {target_group} - {e}")
        
        if not target_groups:
            logger.warning("⚠️ Target guruhlar sozlanmagan! Admin paneldan sozlang.")
        
        logger.info(f"\n👁️ Qo'shimcha kuzatilayotgan guruhlar: {len(monitored_groups)}")
        for group_id in monitored_groups:
            try:
                entity = await self.client.get_entity(group_id)
                title = getattr(entity, 'title', str(group_id))
                logger.info(f"   ✓ {title}")
            except Exception as e:
                logger.warning(f"   ✗ {group_id} - {e}")
    
    async def _import_all_groups(self):
        """Akauntdagi barcha guruhlarni import qilish"""
        try:
            dialogs = await self.client.get_dialogs()
            imported_count = 0
            
            for dialog in dialogs:
                # Faqat guruhlar va kanallar
                if dialog.is_group or dialog.is_channel:
                    group_id = dialog.id
                    title = dialog.title
                    
                    # DB ga qo'shish
                    if db.add_source_group(group_id, title):
                        imported_count += 1
                        logger.debug(f"   ✓ {title} ({group_id})")
            
            logger.info(f"✅ {imported_count} ta guruh import qilindi")
            
        except Exception as e:
            logger.error(f"❌ Guruhlarni import qilishda xato: {e}")
    
    async def _process_message(self, event):
        """Xabarni qayta ishlash"""
        
        try:
            # Guruhni tekshirish
            chat_id = event.chat_id
            source_groups = db.get_active_group_ids()
            monitored_groups = db.get_monitored_groups()
            target_groups = db.get_target_groups()
            
            # Target guruhlardan kelgan xabarlarni ignore qilish (loop oldini olish)
            if chat_id in target_groups:
                return
            
            # Barcha kuzatilayotgan guruhlar
            all_source_groups = source_groups + monitored_groups
            
            if chat_id not in all_source_groups:
                return
            
            message = event.message
            
            # Faqat bizning botimizdan kelgan xabarlarni ignore qilish (loop oldini olish)
            sender = await event.get_sender()
            if sender and getattr(sender, 'bot', False):
                # Bizning bot ID'si
                our_bot_id = (await self.bot.get_me()).id
                if sender.id == our_bot_id:
                    logger.debug(f"🤖 O'z botimiz xabari ignore qilindi")
                    return
                # Boshqa botlardan kelgan xabarlarni qabul qilamiz
            
            text = message.text or message.message or ""
            
            # Stiker yoki emoji bo'lsa, o'tkazib yuborish
            if message.sticker or message.photo or message.video or message.document:
                logger.debug(f"🚫 Stiker/rasm/video filtrlandi")
                return
            
            if not text:
                return
            
            # Juda uzun xabarlarni filtrlash (60 belgidan ko'p)
            if len(text.strip()) > 60:
                logger.debug(f"🚫 Juda uzun xabar filtrlandi ({len(text)} belgi): {truncate_text(text, 40)}")
                self.filtered_count += 1
                db.update_stats(filtered=1)
                return
            
            # Emoji va maxsus belgilarni tekshirish
            # Emoji ko'p bo'lgan xabarlarni filtrlash
            emoji_count = 0
            
            for char in text:
                code = ord(char)
                # Unicode emoji diapazonlari
                if (0x1F300 <= code <= 0x1F9FF or  # Emoji & Pictographs
                    0x2600 <= code <= 0x26FF or    # Miscellaneous Symbols
                    0x2700 <= code <= 0x27BF or    # Dingbats
                    0xFE00 <= code <= 0xFE0F or    # Variation Selectors
                    0x1F000 <= code <= 0x1F02F or  # Mahjong Tiles
                    0x1F0A0 <= code <= 0x1F0FF):   # Playing Cards
                    emoji_count += 1
            
            # Agar emoji 3 tadan ko'p bo'lsa filtrlash
            if emoji_count > 3:
                logger.debug(f"🚫 Emoji ko'p xabar filtrlandi ({emoji_count} emoji): {truncate_text(text, 40)}")
                self.filtered_count += 1
                db.update_stats(filtered=1)
                return
            
            self.processed_count += 1
            
            # Chat ma'lumotlari
            chat = await event.get_chat()
            sender = await event.get_sender()
            
            chat_title = getattr(chat, 'title', 'Unknown')
            sender_name = self._get_sender_name(sender)
            
            logger.debug(f"[{chat_title}] {sender_name}: {truncate_text(text, 50)}")
            
            # Bloklangan foydalanuvchini tekshirish
            user_id = sender.id if sender else 0
            if db.is_blocked(user_id):
                logger.debug(f"🚫 Bloklangan foydalanuvchi: {sender_name} ({user_id})")
                self.filtered_count += 1
                db.update_stats(filtered=1)
                return
            
            # Kalit so'zlarni tekshirish
            driver_keywords = db.get_keywords('driver')
            passenger_keywords = db.get_keywords('passenger')
            text_lower = text.lower()
            
            # Haydovchi kalit so'zlarini tekshirish (filtrlash)
            for kw in driver_keywords:
                if kw['word'].lower() in text_lower:
                    logger.debug(f"🚫 Haydovchi kalit so'zi topildi: '{kw['word']}' - {truncate_text(text, 40)}")
                    self.filtered_count += 1
                    db.update_stats(filtered=1)
                    return
            
            # Yo'lovchi kalit so'zlarini tekshirish (majburiy qabul qilish)
            force_accept = False
            for kw in passenger_keywords:
                if kw['word'].lower() in text_lower:
                    logger.debug(f"✅ Yo'lovchi kalit so'zi topildi: '{kw['word']}' - majburiy qabul qilish")
                    force_accept = True
                    break
            
            # AI klassifikatsiya
            is_order, order_data = await classifier.is_passenger_order(text)
            
            # Yo'lovchi kalit so'zi bo'lsa, majburiy qabul qilish
            if force_accept:
                is_order = True
                if not order_data:
                    order_data = {}
            
            # Agar AI telefon topa olmasa, regex bilan qidirish
            if is_order and order_data:
                if not order_data.get("phone"):
                    from utils import extract_phone_from_text
                    phone = extract_phone_from_text(text)
                    if phone:
                        order_data["phone"] = phone
                        logger.debug(f"📞 Telefon regex bilan topildi: {phone}")
            
            if is_order:
                # Flood oldini olish - bir foydalanuvchidan 30 soniya ichida faqat 1 zakaz
                import time
                current_time = time.time()
                user_id = sender.id if sender else 0
                
                if user_id in self.user_last_order:
                    last_order_time = self.user_last_order[user_id]
                    time_diff = current_time - last_order_time
                    
                    if time_diff < 30:  # 30 soniya ichida
                        logger.debug(f"🚫 Flood: {sender_name} - {int(30 - time_diff)} soniya kutish kerak")
                        self.filtered_count += 1
                        db.update_stats(filtered=1)
                        return
                
                # Zakazni yuborish
                await self._forward_order(event, order_data, chat_title, sender_name)
                
                # Vaqtni saqlash
                self.user_last_order[user_id] = current_time
            else:
                # Haydovchi zakazi tekshirish
                is_driver, driver_data = await classifier.is_driver_order(text)
                
                # Agar AI telefon topa olmasa, regex bilan qidirish
                if is_driver and driver_data:
                    if not driver_data.get("phone"):
                        from utils import extract_phone_from_text
                        phone = extract_phone_from_text(text)
                        if phone:
                            driver_data["phone"] = phone
                            logger.debug(f"📞 Telefon regex bilan topildi: {phone}")
                
                if is_driver:
                    # Flood oldini olish
                    import time
                    current_time = time.time()
                    user_id = sender.id if sender else 0
                    
                    if user_id in self.user_last_order:
                        last_order_time = self.user_last_order[user_id]
                        time_diff = current_time - last_order_time
                        
                        if time_diff < 30:  # 30 soniya ichida
                            logger.debug(f"🚫 Flood: {sender_name} - {int(30 - time_diff)} soniya kutish kerak")
                            self.filtered_count += 1
                            db.update_stats(filtered=1)
                            return
                    
                    # Haydovchi zakazi ham yuborish
                    await self._forward_order(event, driver_data, chat_title, sender_name)
                    
                    # Vaqtni saqlash
                    self.user_last_order[user_id] = current_time
                else:
                    # Boshqa xabar - filtrlash
                    self.filtered_count += 1
                    db.update_stats(filtered=1)
                    logger.debug(f"🚫 Boshqa xabar filtrlandi: {truncate_text(text, 40)}")
            
            db.update_stats(processed=1)
            
        except Exception as e:
            logger.error(f"Xato: {e}", exc_info=True)
            # Adminlarga xabar yuborish
            error_msg = f"❌ **Xatolik yuz berdi!**\n\n"
            error_msg += f"**Xato:** {str(e)}\n"
            error_msg += f"**Guruh:** {chat_title if 'chat_title' in locals() else 'Noma\'lum'}\n"
            error_msg += f"**Xabar:** {truncate_text(text, 100) if 'text' in locals() else 'Noma\'lum'}"
            await self.notify_admins(error_msg)
    
    async def _forward_order(self, event, order_data: dict, chat_title: str, sender_name: str):
        """Buyurtmani barcha target guruhlarga yuborish (bot tokeni orqali)"""
        
        target_groups = db.get_target_groups()
        if not target_groups:
            logger.warning("Target guruhlar sozlanmagan!")
            return
        
        try:
            message = event.message
            original_text = message.text or ""
            
            # Yuboruvchining ID'si va username
            sender = await event.get_sender()
            sender_id = sender.id if sender else None
            sender_username = getattr(sender, 'username', None) if sender else None
            
            # Profil telefon raqamini olishga harakat (agar ommaviy bo'lsa)
            profile_phone = None
            if sender and hasattr(sender, 'phone') and sender.phone:
                profile_phone = sender.phone
                if not profile_phone.startswith('+'):
                    profile_phone = '+' + profile_phone
                logger.debug(f"📞 Profil telefoni topildi: {profile_phone}")
            
            # Agar xabarda telefon yo'q bo'lsa, profil telefonini ishlatish
            if order_data and not order_data.get("phone") and profile_phone:
                order_data["phone"] = profile_phone
                logger.info(f"📞 Profil telefoni ishlatildi: {profile_phone}")
            
            # Asl xabarning linki
            chat = await event.get_chat()
            message_link = None
            if hasattr(chat, 'username') and chat.username:
                # Public guruh
                message_link = f"https://t.me/{chat.username}/{message.id}"
            else:
                # Private guruh - chat ID orqali
                # Private guruhlar uchun: https://t.me/c/[chat_id_without_-100]/[message_id]
                chat_id_str = str(chat.id)
                if chat_id_str.startswith('-100'):
                    clean_chat_id = chat_id_str[4:]  # -100 ni olib tashlash
                    message_link = f"https://t.me/c/{clean_chat_id}/{message.id}"

            
            # Formatlash
            formatted = format_order_message(
                order_data, 
                original_message=original_text,
                message_link=message_link, 
                sender_name=sender_name,
                sender_id=sender_id
            )
            
            # Tugmalar
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            buttons = []
            has_username = False
            
            # Username borligini tekshirish
            if sender and hasattr(sender, 'username') and sender.username:
                has_username = True
            
            # 1. Mijozning ismi tugmasi (faqat tg://user?id orqali)
            if sender_id:
                user_url = f"tg://user?id={sender_id}"
                
                # Ismni qisqartirish (max 25 belgi)
                button_name = sender_name
                if len(button_name) > 25:
                    button_name = button_name[:22] + "..."
                
                buttons.append([InlineKeyboardButton(text=f"👤 {button_name}", url=user_url)])
            
            # 2. Telefon tugmasi (faqat telefon bo'lsa)
            if order_data and order_data.get("phone"):
                phone = order_data['phone']
                # Telefon raqamini tozalash (faqat raqamlar va +)
                clean_phone = "".join(c for c in phone if c.isdigit() or c == "+")
                
                # + belgisini olib tashlash (URL uchun)
                phone_for_url = clean_phone.replace("+", "")
                
                # onmap.uz/tel/ link
                phone_url = f"https://onmap.uz/tel/{phone_for_url}"
                buttons.append([InlineKeyboardButton(text=f"📞 {clean_phone}", url=phone_url)])
            
            # 3. Asl xabar tugmasi (hamma uchun)
            if message_link:
                # Guruh nomini qisqartirish
                button_text = chat_title
                if len(button_text) > 25:
                    button_text = button_text[:22] + "..."
                buttons.append([InlineKeyboardButton(text=f"📨 {button_text}", url=message_link)])
            
            # Tugmalar bo'lmasa ham keyboard None bo'ladi
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
            
            # Barcha target guruhlarga yuborish (bot tokeni orqali)
            success_count = 0
            for target_group in target_groups:
                try:
                    await self.bot.send_message(
                        target_group,
                        formatted,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=keyboard
                    )
                    success_count += 1
                    logger.debug(f"   ✓ Guruh {target_group}ga yuborildi")
                    
                    # Flood oldini olish uchun pauza (0.5 soniya)
                    if success_count < len(target_groups):
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    error_msg = str(e)
                    # Agar tugma xato bo'lsa, tugmasiz yuborishga harakat
                    if "BUTTON_USER_INVALID" in error_msg or "BUTTON" in error_msg:
                        try:
                            logger.debug(f"   ⚠️ Tugma xato, tugmasiz yuborilmoqda...")
                            await self.bot.send_message(
                                target_group,
                                formatted,
                                parse_mode=ParseMode.HTML,
                                disable_web_page_preview=True
                            )
                            success_count += 1
                            logger.debug(f"   ✓ Guruh {target_group}ga tugmasiz yuborildi")
                            
                            if success_count < len(target_groups):
                                await asyncio.sleep(0.5)
                        except Exception as e2:
                            logger.error(f"   ✗ Guruh {target_group}ga yuborishda xato: {e2}")
                    else:
                        logger.error(f"   ✗ Guruh {target_group}ga yuborishda xato: {e}")
            
            self.forwarded_count += 1
            db.update_stats(forwarded=1)
            logger.info(f"✅ Buyurtma {len(target_groups)} ta guruhga yuborildi: {truncate_text(original_text, 40)}")
            
            # Zakazni database'ga saqlash
            phone = order_data.get('phone') if order_data else None
            db.add_order(
                user_id=sender_id,
                user_name=sender_name,
                phone=phone,
                message_text=original_text,
                chat_id=chat.id,
                chat_title=chat_title
            )
            
        except Exception as e:
            logger.error(f"Yuborishda xato: {e}")
    
    def _get_sender_name(self, sender) -> str:
        """Yuboruvchi ismi (username siz)"""
        if not sender:
            return "Noma'lum"
        
        parts = []
        if hasattr(sender, 'first_name') and sender.first_name:
            parts.append(sender.first_name)
        if hasattr(sender, 'last_name') and sender.last_name:
            parts.append(sender.last_name)
        
        name = " ".join(parts) if parts else "Foydalanuvchi"
        
        return name


async def main():
    """Main"""
    userbot = TaxiUserbot()
    await userbot.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Userbot to'xtatildi")
