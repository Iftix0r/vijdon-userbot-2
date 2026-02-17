"""
Telegram Taxi Bot - AI Message Classifier
OpenAI API orqali xabarlarni tahlil qiladi
Yaxshilangan versiya - yo'lovchi va haydovchi zakazlarini ajratadi
"""

import json
import logging
from openai import AsyncOpenAI
from config import Config
import database as db

logger = logging.getLogger("taxi_bot.classifier")


# Default AI prompt
DEFAULT_PROMPT = """Sen taxi xabarlarini tahlil qiluvchi AI assistantsan.
Senga Telegram guruhlaridan xabarlar keladi. Har bir xabarni tahlil qilib, quyidagi formatda JSON javob ber:

{
    "type": "passenger_order" | "driver_order" | "other",
    "confidence": 0.0-1.0,
    "data": {
        "from_location": "Qayerdan (manzil/shahar)",
        "to_location": "Qayerga (manzil/shahar)",
        "time": "Vaqt (bugun, ertaga, soat, sana)",
        "passengers": "Yo'lovchilar soni",
        "phone": "Telefon raqami",
        "price": "Narx",
        "car_info": "Mashina markasi/rangi (agar haydovchi bo'lsa)",
        "notes": "Qo'shimcha ma'lumotlar"
    }
}

MUHIM QOIDALAR:

1. **passenger_order** - YO'LOVCHI taksi/pochta qidiryapti:
   - "Kerak", "boraman", "boramiz", "ketaman", "ketamiz" kabi so'zlar
   - "Olib keting", "taxi kerak", "mashina kerak"
   - Manzillar ko'rsatilgan (shahardan shaharga yoki manzildan manzilga)
   - Telefon raqami bo'lishi mumkin
   - "Pochta bor", "jo'natma bor" - pochta yuborish ham passenger_order

2. **driver_order** - HAYDOVCHI yo'lovchi/pochta qidiryapti:
   - "Olib ketaman", "olaman", "ketamiz" (1-shaxs ko'plik)
   - "Bo'sh joy bor", "joy bor", "mashina ketadi"
   - "Pochta olaman", "jo'natma olaman"
   - Mashina markasi/rangi aytilgan ("Cobalt", "Lacetti", "Nexia")
   - Haydovchi o'zini taklif qilyapti

3. **other** - Taxi bilan aloqasi yo'q (salom, savol, muhokama, reklama)

MUHIM:
- Ikkalasi ham ZAKAZ hisoblanadi - har ikkisini data bilan qaytarish kerak
- confidence - ishonch darajasi (0.7 dan yuqori bo'lsa qabul qilinadi)
- O'zbek, rus, ingliz tillarida xabarlar kelishi mumkin
- Shahar nomlari: Toshkent, Samarqand, Buxoro, Andijon, Farg'ona, Namangan va boshqalar

MISOLLAR:
- "Toshkent-Samarqand 2ta odam" → passenger_order
- "Samarqanddan Toshkentga cobalt ketadi" → driver_order  
- "Pochta Toshkentdan Buxoroga" → passenger_order
- "Buxorodan pochta olaman" → driver_order

Faqat JSON formatda javob ber, boshqa hech narsa yozma."""


class MessageClassifier:
    """OpenAI orqali xabarlarni klassifikatsiya qilish"""
    
    # Xabar turlari
    PASSENGER_ORDER = "passenger_order"
    DRIVER_ORDER = "driver_order"
    OTHER = "other"
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
    
    def _get_prompt(self) -> str:
        """AI promptni olish (DB dan yoki default)"""
        custom_prompt = db.get_setting("ai_prompt")
        return custom_prompt if custom_prompt else DEFAULT_PROMPT
    
    async def classify_message(self, message_text: str) -> dict:
        """
        Xabarni tahlil qilish
        
        Returns:
            dict: {
                "type": "passenger_order" | "driver_order" | "other",
                "confidence": 0.0-1.0,
                "data": {...}
            }
        """
        
        if not message_text or len(message_text.strip()) < 5:
            return {"type": self.OTHER, "confidence": 1.0, "data": None}
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_prompt()
                    },
                    {
                        "role": "user",
                        "content": message_text
                    }
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.debug(f"AI natija: {result}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse xatosi: {e}")
            return {"type": self.OTHER, "confidence": 0.0, "data": None}
            
        except Exception as e:
            logger.error(f"OpenAI API xatosi: {e}")
            return {"type": self.OTHER, "confidence": 0.0, "data": None}
    
    async def is_order(self, message_text: str) -> tuple[bool, str, dict | None]:
        """
        Xabar zakaz (yo'lovchi yoki haydovchi) mi tekshirish
        
        Returns:
            (bool, str, dict | None): (zakazmi, turi, ma'lumotlar)
        """
        
        result = await self.classify_message(message_text)
        order_type = result.get("type", self.OTHER)
        confidence = result.get("confidence", 0)
        
        if order_type in [self.PASSENGER_ORDER, self.DRIVER_ORDER]:
            if confidence >= 0.7:
                return True, order_type, result.get("data")
        
        return False, self.OTHER, None
    
    async def is_passenger_order(self, message_text: str) -> tuple[bool, dict | None]:
        """Yo'lovchi zakazi tekshirish (orqaga muvofiqlik)"""
        is_ord, order_type, data = await self.is_order(message_text)
        if is_ord and order_type == self.PASSENGER_ORDER:
            return True, data
        return False, None
    
    async def is_driver_order(self, message_text: str) -> tuple[bool, dict | None]:
        """Haydovchi zakazi tekshirish"""
        is_ord, order_type, data = await self.is_order(message_text)
        if is_ord and order_type == self.DRIVER_ORDER:
            return True, data
        return False, None


# Singleton instance
classifier = MessageClassifier()
