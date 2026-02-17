import os
from dotenv import load_dotenv

load_dotenv()                                                                                                                                                                                                                                                                                           


class Config:
    """Asosiy sozlamalar"""
    
    # Telegram Bot Token (admin panel uchun)
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    
    # Telegram API (userbot uchun)
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
    SESSION_NAME = os.getenv("SESSION_NAME", "taxi_userbot")
    # If true, import all joined groups/channels into monitored source groups on startup
    IMPORT_JOINED_GROUPS = os.getenv("IMPORT_JOINED_GROUPS", "false").lower() in ("1", "true", "yes")
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Super Adminlar (birinchi marta setup uchun)
    SUPER_ADMIN_IDS = []
    
    @classmethod
    def load_super_admins(cls):
        """Super adminlarni yuklash"""
        admins_str = os.getenv("SUPER_ADMIN_IDS", "")
        if admins_str:
            cls.SUPER_ADMIN_IDS = [int(x.strip()) for x in admins_str.split(",") if x.strip()]
        return cls.SUPER_ADMIN_IDS
    
    @classmethod
    def validate_bot(cls):
        """Bot sozlamalarini tekshirish"""
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN kiritilmagan")
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY kiritilmagan")
        
        cls.load_super_admins()
        
        if errors:
            raise ValueError("Sozlamalarda xatoliklar:\n" + "\n".join(f"- {e}" for e in errors))
        
        return True
    
    @classmethod
    def validate_userbot(cls):
        """Userbot sozlamalarini tekshirish"""
        errors = []
        
        if not cls.API_ID:
            errors.append("API_ID kiritilmagan")
        if not cls.API_HASH:
            errors.append("API_HASH kiritilmagan")
        
        if errors:
            raise ValueError("Sozlamalarda xatoliklar:\n" + "\n".join(f"- {e}" for e in errors))
        
        return True


# Boshlang'ich yuklash
Config.load_super_admins()
