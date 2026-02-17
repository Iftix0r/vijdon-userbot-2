# Vijdon Taxi Bot

Telegram taxi bot - guruhlardan zakazlarni avtomatik kuzatish va yuborish tizimi.

## Xususiyatlar

- 🤖 **Userbot** - Telethon orqali guruhlardan xabarlarni kuzatish
- 🚕 **Admin Panel** - Aiogram orqali botni boshqarish
- 🧠 **AI Klassifikatsiya** - OpenAI orqali yo'lovchi/haydovchi zakazlarini aniqlash
- 📊 **Statistika** - Qayta ishlangan, yuborilgan va filtrlangan xabarlar statistikasi
- 🔑 **Kalit so'zlar** - Haydovchi va yo'lovchi kalit so'zlari bilan filtrlash
- 📞 **Telefon aniqlash** - AI va regex orqali telefon raqamlarni topish
- 🚫 **Emoji filtri** - Ko'p emoji bo'lgan xabarlarni filtrlash
- ⏱️ **Flood himoyasi** - Bir foydalanuvchidan 30 soniya ichida faqat 1 zakaz

## O'rnatish

1. Repository'ni klonlash:
```bash
git clone https://github.com/Iftix0r/vijdon-userbot-2.git
cd vijdon-userbot-2
```

2. Virtual environment yaratish:
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# yoki
venv\Scripts\activate  # Windows
```

3. Kerakli paketlarni o'rnatish:
```bash
pip install -r requirements.txt
```

4. `.env` fayl yaratish va sozlash:
```bash
cp .env.example .env
nano .env
```

`.env` faylda quyidagilarni to'ldiring:
```env
# Bot sozlamalari
BOT_TOKEN=your_bot_token_here
SUPER_ADMIN_IDS=123456789,987654321

# Userbot sozlamalari (Telethon)
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=+998901234567
SESSION_NAME=taxi_userbot

# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Sozlamalar
IMPORT_JOINED_GROUPS=true
```

## Ishga tushirish

### Birinchi marta ishga tushirish

1. Userbot'ni ishga tushiring (Telegram'ga kirish uchun):
```bash
python userbot.py
```

Telefon raqamingizga kelgan kodni kiriting.

2. Admin panel'ni ishga tushiring:
```bash
python bot.py
```

### Keyingi safar

Ikkala botni bir vaqtda ishga tushirish:
```bash
bash start.sh
```

## Foydalanish

1. Botga `/start` buyrug'ini yuboring
2. Admin paneldan:
   - Guruhlar qo'shing (kuzatiladigan guruhlar)
   - Target guruh qo'shing (zakazlar yuboriladigan guruh)
   - Kalit so'zlar qo'shing (haydovchi/yo'lovchi)
   - Statistikani ko'ring

## Kalit so'zlar

### Haydovchi kalit so'zlari
Agar xabarda bu so'zlar bo'lsa, zakaz qabul qilinmaydi:
- ketaman
- yuryapman
- bo'shman
- mashina bor

### Yo'lovchi kalit so'zlari
Agar xabarda bu so'zlar bo'lsa, majburiy qabul qilinadi:
- odam kerak
- pochta olamiz
- yo'lovchi kerak
- odam olamiz

## Filtrlar

- ❌ 3 tadan ko'p emoji
- ❌ 60 belgidan ko'p matn
- ❌ Stiker, rasm, video
- ❌ Bot xabarlari (o'z botidan tashqari)
- ❌ Target guruhlardan kelgan xabarlar (loop oldini olish)
- ❌ Haydovchi kalit so'zlari

## Texnologiyalar

- Python 3.8+
- Aiogram 3.x (Bot API)
- Telethon (Userbot)
- OpenAI API (AI klassifikatsiya)
- SQLite (Database)

## Litsenziya

MIT License

## Muallif

Vijdon Taxi Team
# vijdon-userbot-2
