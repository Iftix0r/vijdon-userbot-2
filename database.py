"""
Telegram Taxi Bot - Database Module
SQLite database bilan ishlash
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger("taxi_bot.database")

DATABASE_PATH = "data.db"


@contextmanager
def get_connection():
    """Database connection context manager"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """Database jadvallarini yaratish"""
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Adminlar jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_super_admin BOOLEAN DEFAULT 0
            )
        """)
        
        # Kuzatiladigan guruhlar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER UNIQUE NOT NULL,
                title TEXT,
                username TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by INTEGER,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        # Sozlamalar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Statistika
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE DEFAULT (date('now')),
                processed INTEGER DEFAULT 0,
                forwarded INTEGER DEFAULT 0,
                filtered INTEGER DEFAULT 0
            )
        """)
        
        # Foydalanuvchi zakazlari (kunlik limit uchun)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date DATE DEFAULT (date('now')),
                order_count INTEGER DEFAULT 0,
                last_order_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, date)
            )
        """)
        
        # Bloklangan foydalanuvchilar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blocked_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                blocked_by INTEGER,
                blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT
            )
        """)
        
        # Kalit so'zlar (Keywords)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                type TEXT NOT NULL,
                added_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(word, type)
            )
        """)
        
        # Zakazlar tarixi
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                phone TEXT,
                message_text TEXT,
                chat_id INTEGER,
                chat_title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        logger.info("✅ Database yaratildi yoki mavjud")


# ============== ADMIN FUNCTIONS ==============

def add_admin(user_id: int, username: str = None, full_name: str = None, is_super: bool = False) -> bool:
    """Admin qo'shish"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO admins (user_id, username, full_name, is_super_admin)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, full_name, is_super))
            return True
    except Exception as e:
        logger.error(f"Admin qo'shishda xato: {e}")
        return False


def remove_admin(user_id: int) -> bool:
    """Adminni o'chirish"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admins WHERE user_id = ? AND is_super_admin = 0", (user_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Admin o'chirishda xato: {e}")
        return False


def is_admin(user_id: int) -> bool:
    """Foydalanuvchi adminmi tekshirish"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None


def is_super_admin(user_id: int) -> bool:
    """Super adminmi tekshirish"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM admins WHERE user_id = ? AND is_super_admin = 1", (user_id,))
        return cursor.fetchone() is not None


def get_all_admins() -> List[Dict]:
    """Barcha adminlarni olish"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins ORDER BY is_super_admin DESC, added_at")
        return [dict(row) for row in cursor.fetchall()]


# ============== SOURCE GROUPS FUNCTIONS ==============

def add_source_group(group_id: int, title: str = None, username: str = None, added_by: int = None) -> bool:
    """Kuzatiladigan guruh qo'shish"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO source_groups (group_id, title, username, added_by, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (group_id, title, username, added_by))
            return True
    except Exception as e:
        logger.error(f"Guruh qo'shishda xato: {e}")
        return False


def remove_source_group(group_id: int) -> bool:
    """Guruhni o'chirish"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM source_groups WHERE group_id = ?", (group_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Guruh o'chirishda xato: {e}")
        return False


def toggle_source_group(group_id: int) -> bool:
    """Guruhni yoqish/o'chirish"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE source_groups SET is_active = NOT is_active WHERE group_id = ?
            """, (group_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Guruh toggle qilishda xato: {e}")
        return False


def get_source_groups(active_only: bool = False) -> List[Dict]:
    """Guruhlar ro'yxatini olish"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM source_groups WHERE is_active = 1 ORDER BY added_at")
        else:
            cursor.execute("SELECT * FROM source_groups ORDER BY is_active DESC, added_at")
        return [dict(row) for row in cursor.fetchall()]


def get_active_group_ids() -> List[int]:
    """Faol guruh ID'larini olish"""
    groups = get_source_groups(active_only=True)
    return [g['group_id'] for g in groups]


# ============== SETTINGS FUNCTIONS ==============

def set_setting(key: str, value: str) -> bool:
    """Sozlama saqlash"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
            return True
    except Exception as e:
        logger.error(f"Sozlama saqlashda xato: {e}")
        return False


def get_setting(key: str, default: str = None) -> Optional[str]:
    """Sozlamani olish"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default


def get_target_groups() -> List[int]:
    """Target guruhlarni olish (bir nechta)"""
    value = get_setting("target_groups")
    if value:
        try:
            return [int(x.strip()) for x in value.split(",") if x.strip()]
        except:
            return []
    
    # Eski sozlamani tekshirish (migratsiya uchun)
    old_value = get_setting("target_group")
    if old_value:
        # Yangi formatga o'tkazish
        set_setting("target_groups", old_value)
        set_setting("target_group", "") # Eskisini o'chirish
        return [int(old_value)]
        
    return []


def add_target_group(group_id: int) -> bool:
    """Target guruh qo'shish"""
    groups = get_target_groups()
    if group_id not in groups:
        groups.append(group_id)
        return set_setting("target_groups", ",".join(map(str, groups)))
    return True


def remove_target_group(group_id: int) -> bool:
    """Target guruhni olib tashlash"""
    groups = get_target_groups()
    if group_id in groups:
        groups.remove(group_id)
        return set_setting("target_groups", ",".join(map(str, groups)))
    return False


# Eskilik (kodni buzmaslik uchun alias), lekin list'ning birinchisini qaytaradi
def get_target_group() -> Optional[int]:
    """Target guruhni olish (asosiy) - compatibility uchun"""
    groups = get_target_groups()
    return groups[0] if groups else None


# ============== MONITORED GROUPS FUNCTIONS ==============

def get_monitored_groups() -> List[int]:
    """Qo'shimcha kuzatilayotgan guruhlarni olish"""
    value = get_setting("monitored_groups")
    if value:
        try:
            return [int(x.strip()) for x in value.split(",") if x.strip()]
        except:
            return []
    return []


def add_monitored_group(group_id: int) -> bool:
    """Qo'shimcha kuzatilayotgan guruh qo'shish"""
    groups = get_monitored_groups()
    if group_id not in groups:
        groups.append(group_id)
        return set_setting("monitored_groups", ",".join(map(str, groups)))
    return True


def remove_monitored_group(group_id: int) -> bool:
    """Qo'shimcha kuzatilayotgan guruhni olib tashlash"""
    groups = get_monitored_groups()
    if group_id in groups:
        groups.remove(group_id)
        return set_setting("monitored_groups", ",".join(map(str, groups)))
    return False


# ============== STATS FUNCTIONS ==============

def update_stats(processed: int = 0, forwarded: int = 0, filtered: int = 0):
    """Statistikani yangilash"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Bugungi yozuv bormi tekshirish
            cursor.execute("SELECT id FROM stats WHERE date = ?", (today,))
            row = cursor.fetchone()
            
            if row:
                cursor.execute("""
                    UPDATE stats SET 
                        processed = processed + ?,
                        forwarded = forwarded + ?,
                        filtered = filtered + ?
                    WHERE date = ?
                """, (processed, forwarded, filtered, today))
            else:
                cursor.execute("""
                    INSERT INTO stats (date, processed, forwarded, filtered)
                    VALUES (?, ?, ?, ?)
                """, (today, processed, forwarded, filtered))
    except Exception as e:
        logger.error(f"Statistika yangilashda xato: {e}")


def get_today_stats() -> Dict:
    """Bugungi statistika"""
    with get_connection() as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT * FROM stats WHERE date = ?", (today,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {"processed": 0, "forwarded": 0, "filtered": 0}


def get_total_stats() -> Dict:
    """Umumiy statistika"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COALESCE(SUM(processed), 0) as processed,
                COALESCE(SUM(forwarded), 0) as forwarded,
                COALESCE(SUM(filtered), 0) as filtered
            FROM stats
        """)
        row = cursor.fetchone()
        return dict(row) if row else {"processed": 0, "forwarded": 0, "filtered": 0}


# ============== USER ORDER LIMIT FUNCTIONS ==============

MAX_ORDERS_PER_DAY = 3  # Kunlik maksimal zakaz soni

def check_user_daily_limit(user_id: int) -> bool:
    """Foydalanuvchi kunlik limitdan o'tganmi tekshirish
    
    Returns:
        True - yana zakaz qilishi mumkin
        False - limit tugagan
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            "SELECT order_count FROM user_orders WHERE user_id = ? AND date = ?",
            (user_id, today)
        )
        row = cursor.fetchone()
        
        if row:
            return row['order_count'] < MAX_ORDERS_PER_DAY
        return True  # Hali zakaz qilmagan


def increment_user_order_count(user_id: int) -> int:
    """Foydalanuvchi zakaz sonini oshirish
    
    Returns:
        Yangi zakaz soni
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute(
                "SELECT order_count FROM user_orders WHERE user_id = ? AND date = ?",
                (user_id, today)
            )
            row = cursor.fetchone()
            
            if row:
                new_count = row['order_count'] + 1
                cursor.execute(
                    "UPDATE user_orders SET order_count = ?, last_order_at = CURRENT_TIMESTAMP WHERE user_id = ? AND date = ?",
                    (new_count, user_id, today)
                )
            else:
                new_count = 1
                cursor.execute(
                    "INSERT INTO user_orders (user_id, date, order_count) VALUES (?, ?, ?)",
                    (user_id, today, new_count)
                )
            
            return new_count
    except Exception as e:
        logger.error(f"Zakaz sonini oshirishda xato: {e}")
        return 0


def get_user_order_count(user_id: int) -> int:
    """Foydalanuvchining bugungi zakaz sonini olish"""
    with get_connection() as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            "SELECT order_count FROM user_orders WHERE user_id = ? AND date = ?",
            (user_id, today)
        )
        row = cursor.fetchone()
        return row['order_count'] if row else 0


# ============== BLOCKED USERS FUNCTIONS ==============

def block_user(user_id: int, blocked_by: int = None, reason: str = None) -> bool:
    """Foydalanuvchini bloklash"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO blocked_users (user_id, blocked_by, reason)
                VALUES (?, ?, ?)
            """, (user_id, blocked_by, reason))
            return True
    except Exception as e:
        logger.error(f"Bloklashda xato: {e}")
        return False


def unblock_user(user_id: int) -> bool:
    """Foydalanuvchini blokdan chiqarish"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM blocked_users WHERE user_id = ?", (user_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Blokdan chiqarishda xato: {e}")
        return False


def is_blocked(user_id: int) -> bool:
    """Foydalanuvchi bloklangan mi tekshirish"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM blocked_users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None


def get_blocked_users() -> List[Dict]:
    """Bloklangan foydalanuvchilar ro'yxati"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blocked_users ORDER BY blocked_at DESC")
        return [dict(row) for row in cursor.fetchall()]


# ============== KEYWORD FUNCTIONS ==============

def add_keyword(word: str, ktype: str, added_by: int = None) -> bool:
    """Kalit so'z qo'shish (driver/passenger)"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO keywords (word, type, added_by)
                VALUES (?, ?, ?)
            """, (word.lower().strip(), ktype, added_by))
            return True
    except Exception as e:
        logger.error(f"Keyword qo'shishda xato: {e}")
        return False


def remove_keyword(word_id: int) -> bool:
    """Kalit so'zni o'chirish"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM keywords WHERE id = ?", (word_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Keyword o'chirishda xato: {e}")
        return False


def get_keywords(ktype: str = None) -> List[Dict]:
    """Kalit so'zlarni olish"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if ktype:
            cursor.execute("SELECT * FROM keywords WHERE type = ? ORDER BY word", (ktype,))
        else:
            cursor.execute("SELECT * FROM keywords ORDER BY type, word")
        return [dict(row) for row in cursor.fetchall()]


# ============== ORDERS FUNCTIONS ==============

def add_order(user_id: int, user_name: str, phone: str, message_text: str, 
              chat_id: int, chat_title: str) -> bool:
    """Zakazni saqlash"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (user_id, user_name, phone, message_text, chat_id, chat_title)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, user_name, phone, message_text, chat_id, chat_title))
            return True
    except Exception as e:
        logger.error(f"Zakaz saqlashda xato: {e}")
        return False


def get_recent_orders(limit: int = 10) -> List[Dict]:
    """So'nggi zakazlarni olish"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM orders 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


# Initialize on import
init_database()
