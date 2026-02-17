#!/bin/bash

echo "🛑 Botlarni to'xtatish..."

# Bot processlarini topish va to'xtatish
BOT_PIDS=$(ps aux | grep -E 'python.*bot\.py' | grep -v grep | awk '{print $2}')
USERBOT_PIDS=$(ps aux | grep -E 'python.*userbot\.py' | grep -v grep | awk '{print $2}')

if [ -z "$BOT_PIDS" ] && [ -z "$USERBOT_PIDS" ]; then
    echo "❌ Hech qanday bot jarayoni topilmadi"
    exit 0
fi

# Bot'ni to'xtatish
if [ ! -z "$BOT_PIDS" ]; then
    echo "🤖 Admin panel to'xtatilmoqda..."
    for pid in $BOT_PIDS; do
        kill $pid 2>/dev/null
        echo "   ✓ Bot process $pid to'xtatildi"
    done
fi

# Userbot'ni to'xtatish
if [ ! -z "$USERBOT_PIDS" ]; then
    echo "🚕 Userbot to'xtatilmoqda..."
    for pid in $USERBOT_PIDS; do
        kill $pid 2>/dev/null
        echo "   ✓ Userbot process $pid to'xtatildi"
    done
fi

# Bir oz kutish
sleep 1

# Agar hali ham ishlayotgan bo'lsa, majburiy to'xtatish
BOT_PIDS=$(ps aux | grep -E 'python.*bot\.py' | grep -v grep | awk '{print $2}')
USERBOT_PIDS=$(ps aux | grep -E 'python.*userbot\.py' | grep -v grep | awk '{print $2}')

if [ ! -z "$BOT_PIDS" ]; then
    echo "⚠️  Bot hali ham ishlayapti, majburiy to'xtatish..."
    for pid in $BOT_PIDS; do
        kill -9 $pid 2>/dev/null
    done
fi

if [ ! -z "$USERBOT_PIDS" ]; then
    echo "⚠️  Userbot hali ham ishlayapti, majburiy to'xtatish..."
    for pid in $USERBOT_PIDS; do
        kill -9 $pid 2>/dev/null
    done
fi

echo ""
echo "✅ Barcha botlar to'xtatildi!"
echo ""
echo "📋 Qayta ishga tushirish uchun:"
echo "   bash start.sh"
echo ""
