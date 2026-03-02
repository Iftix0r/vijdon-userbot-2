#!/bin/bash

# Venv activate
source venv/bin/activate

# Old processes kill if exists
echo "🛑 Eski processlar to'xtatilmoqda..."
pkill -f "python.*main.py"
pkill -f "python.*bot.py"
pkill -f "python.*userbot.py"

# Wait a bit
sleep 2

# Start main (bot + userbot together)
echo "🚕 Taxi Bot ishga tushirilmoqda..."
nohup python -u main.py > nohup_bot.out 2>&1 &
BOT_PID=$!

# Wait for bot to start
sleep 2

echo ""
echo "✅ Bot ishga tushirildi!"
echo ""
echo "📊 Process:"
echo "   Main Bot PID: $BOT_PID"
echo ""
echo "📋 Loglarni ko'rish:"
echo "   tail -f nohup_bot.out"
echo ""
echo "🛑 Botni to'xtatish:"
echo "   pkill -f 'python.*main.py'"
