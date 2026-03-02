#!/usr/bin/env python3
"""
Zakaz formatini test qilish
"""

from utils import format_order_message

# Test ma'lumotlari
test_cases = [
    {
        "name": "To'liq ma'lumotli zakaz",
        "order_data": {
            "from_location": "Chilonzor 9",
            "to_location": "Sergeli 5",
            "passengers": "2",
            "phone": "+998901234567"
        },
        "original_message": "Chilonzor 9 dan Sergeli 5 ga 2 kishi kerak +998901234567",
        "sender_name": "Alisher Valiyev",
        "sender_id": 123456789
    },
    {
        "name": "Telefonsiz zakaz",
        "order_data": {
            "from_location": "Yunusobod",
            "to_location": "Qoyliq",
            "passengers": "3"
        },
        "original_message": "Yunusobod dan Qoyliq ga 3 kishi",
        "sender_name": "Sardor",
        "sender_id": 987654321
    },
    {
        "name": "Minimal zakaz",
        "order_data": None,
        "original_message": "Olmazor dan Chorsu ga kerak",
        "sender_name": "Nodir",
        "sender_id": 111222333
    }
]

print("=" * 60)
print("ZAKAZ FORMAT TEST")
print("=" * 60)

for i, test in enumerate(test_cases, 1):
    print(f"\n{i}. {test['name']}")
    print("-" * 60)
    
    formatted = format_order_message(
        order_data=test['order_data'],
        original_message=test['original_message'],
        sender_name=test['sender_name'],
        sender_id=test['sender_id']
    )
    
    print(formatted)
    print()
    
    # Knopkalar haqida ma'lumot
    print("Knopkalar:")
    print(f"  👤 {test['sender_name'][:20]} - Profil")
    
    if test['order_data'] and test['order_data'].get('phone'):
        print(f"  📞 {test['order_data']['phone']} - Telefon")
    
    print("-" * 60)

print("\n✅ Test tugadi!")
