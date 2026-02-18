"""
Telegram Taxi Userbot - Utility Functions
Yordamchi funksiyalar va logging
"""

import logging
import sys
from datetime import datetime


def setup_logging(level=logging.INFO):
    """Logging sozlash"""
    
    # Log format
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Root logger sozlash
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("taxi_bot.log", encoding="utf-8")
        ]
    )
    
    # Telethon loglarini kamaytirish
    logging.getLogger("telethon").setLevel(logging.WARNING)
    
    return logging.getLogger("taxi_bot")


def format_order_message(order_data: dict, original_message: str = None, 
                         type_emoji: str = "🚕", type_text: str = "BUYURTMA",
                         message_link: str = None, sender_name: str = None, sender_id: int = None) -> str:
    """
    Buyurtma xabarini formatlash (HTML format)
    
    Args:
        order_data: AI dan qaytgan ma'lumotlar
        original_message: Asl xabar matni
        type_emoji: Zakaz turi emojisi
        type_text: Zakaz turi nomi
        message_link: Asl xabarning linki
        sender_name: Yuboruvchining ismi
        sender_id: Yuboruvchining Telegram ID'si
    
    Returns:
        Formatlangan xabar (HTML)
    """
    
    lines = [
        "Asalomu alaykum Hurmatli Vijdon Taxi haydovchilari",
        "Yangi Buyurtma Keldi 😊",
        ""
    ]
    
    # Ismi (profilga link)
    if sender_name and sender_id:
        safe_name = sender_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        user_link = f'<a href="tg://user?id={sender_id}">{safe_name}</a>'
        lines.append(f"👤 {user_link}")
    elif sender_name:
        safe_name = sender_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        lines.append(f"👤 {safe_name}")
    
    lines.append("")  # Bo'sh qator
    
    # Telefon (agar bo'lsa)
    if order_data and order_data.get("phone"):
        lines.append(f"📞 {order_data['phone']}")
    
    lines.append("")  # Bo'sh qator
    
    # Asl xabar matni (qisqartirilgan, link bilan)
    if original_message:
        short_text = truncate_text(original_message, 100)
        # HTML maxsus belgilarini escape qilish
        safe_text = short_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Agar message_link bo'lsa, xabar matnini link qilish
        if message_link:
            lines.append(f"💬 <a href='{message_link}'>{safe_text}</a>")
        else:
            lines.append(f"💬 {safe_text}")
    
    return "\n".join(lines)


def clean_text(text: str) -> str:
    """Matnni tozalash"""
    if not text:
        return ""
    
    # Ortiqcha bo'shliqlarni olib tashlash
    text = " ".join(text.split())
    
    return text.strip()


def is_valid_phone(phone: str) -> bool:
    """Telefon raqamini tekshirish"""
    if not phone:
        return False
    
    # Faqat raqamlar va + belgisini qoldirish
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
    
    # O'zbekiston raqamlari uchun tekshirish
    if cleaned.startswith("+998"):
        return len(cleaned) == 13
    elif cleaned.startswith("998"):
        return len(cleaned) == 12
    elif cleaned.startswith("9"):
        return len(cleaned) == 9
    
    return len(cleaned) >= 9


def extract_phone_from_text(text: str) -> str:
    """Matndan telefon raqamni topish (regex)"""
    import re
    
    if not text:
        return None
    
    # O'zbekiston telefon raqamlari uchun pattern
    patterns = [
        r'\+998\s*\d{2}\s*\d{3}\s*\d{2}\s*\d{2}',  # +998 XX XXX XX XX
        r'\+998\d{9}',  # +998XXXXXXXXX
        r'998\d{9}',    # 998XXXXXXXXX
        r'\b9[0-9]\s*\d{3}\s*\d{2}\s*\d{2}\b',  # 9X XXX XX XX
        r'\b9[0-9]\d{7}\b',  # 9XXXXXXXX
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            phone = match.group(0)
            # Bo'shliqlarni olib tashlash
            phone = phone.replace(' ', '')
            # Agar + yo'q bo'lsa va 998 bilan boshlanmasa, +998 qo'shish
            if not phone.startswith('+'):
                if phone.startswith('998'):
                    phone = '+' + phone
                elif phone.startswith('9'):
                    phone = '+998' + phone
            return phone
    
    return None


def truncate_text(text: str, max_length: int = 100) -> str:
    """Matnni qisqartirish"""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."
