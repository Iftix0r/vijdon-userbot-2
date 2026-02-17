#!/bin/bash

# Venv activate
source venv/bin/activate

# Old processes kill if exists
echo "🛑 Eski processlar to'xtatilmoqda..."
pkill -f "python.*bot.py"
pkill -f "python.*userbot.py"

# Wait a bit
sleep 2

# Start admin panel
echo "🤖 Admin panel ishga tushirilmoqda..."
nohup python -u bot.py > nohup_bot.out 2>&1 &
BOT_PID=$!

# Wait for bot to start
sleep 1

# Start userbot
echo "🚕 Userbot ishga tushirilmoqda..."
nohup python -u userbot.py > nohup_userbot.out 2>&1 &
USERBOT_PID=$!

# Wait a bit
sleep 1

echo ""
echo "✅ Botlar ishga tushirildi!"
echo ""
echo "📊 Processlar:"
echo "   Bot PID: $BOT_PID"
echo "   Userbot PID: $USERBOT_PID"
echo ""
echo "📋 Loglarni ko'rish:"
echo "   Admin panel:  tail -f nohup_bot.out"
echo "   Userbot:      tail -f nohup_userbot.out"
echo "   Ikkalasi:     tail -f nohup_*.out"
echo ""
echo "🛑 Botlarni to'xtatish:"
echo "   pkill -f 'python.*bot.py'"
