"""
Telegram Taxi Bot - Admin Panel Handlers
Aiogram bilan admin panel
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

import database as db
from config import Config

logger = logging.getLogger("taxi_bot.admin")

router = Router()


async def safe_edit_text(message_obj, text, reply_markup=None, parse_mode="Markdown"):
    """Try to edit message with parse mode, fallback to plain text on parse errors."""
    try:
        await message_obj.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest:
        try:
            await message_obj.edit_text(text, reply_markup=reply_markup, parse_mode=None)
        except Exception:
            logger.exception("Failed to edit message, sending as new message")
            await message_obj.answer(text, reply_markup=reply_markup)


# ============== FSM STATES ==============

class AddGroupState(StatesGroup):
    waiting_for_group = State()


class SetTargetState(StatesGroup):
    waiting_for_group = State()


class AddAdminState(StatesGroup):
    waiting_for_user = State()


class AIPromptState(StatesGroup):
    waiting_for_prompt = State()


class AddKeywordState(StatesGroup):
    waiting_for_word = State()


class AddMonitoredGroupState(StatesGroup):
    waiting_for_group = State()


class ListGroupsState(StatesGroup):
    page = State()


# ============== KEYBOARDS ==============

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Asosiy menu"""
    buttons = [
        [InlineKeyboardButton(text="📋 Guruhlar", callback_data="groups_menu")],
        [InlineKeyboardButton(text="📤 Buyurtmalar guruhlari", callback_data="target_menu")],
        [InlineKeyboardButton(text="👁️ Qo'shimcha kuzatilayotgan", callback_data="monitored_menu")],
        [InlineKeyboardButton(text="🔑 Kalit so'zlar", callback_data="keywords_menu")],
        [InlineKeyboardButton(text="🤖 AI Sozlamalari", callback_data="ai_menu")],
        [InlineKeyboardButton(text="👥 Adminlar", callback_data="admins_menu")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def groups_menu_keyboard() -> InlineKeyboardMarkup:
    """Guruhlar menu"""
    buttons = [
        [InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data="add_group")],
        [InlineKeyboardButton(text="📝 Guruhlar ro'yxati", callback_data="list_groups")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admins_menu_keyboard() -> InlineKeyboardMarkup:
    """Adminlar menu"""
    buttons = [
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_admin")],
        [InlineKeyboardButton(text="📝 Adminlar ro'yxati", callback_data="list_admins")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_keyboard(callback: str = "main_menu") -> InlineKeyboardMarkup:
    """Orqaga tugmasi"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=callback)]
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Bekor qilish"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])


# ============== MIDDLEWARE ==============

def is_admin(user_id: int) -> bool:
    """Admin tekshirish"""
    # Super admin
    if user_id in Config.SUPER_ADMIN_IDS:
        return True
    # Database admin
    return db.is_admin(user_id)


# ============== HANDLERS ==============

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Start buyrug'i"""
    user_id = message.from_user.id
    
    # Super adminni DB ga qo'shish
    if user_id in Config.SUPER_ADMIN_IDS:
        db.add_admin(
            user_id=user_id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            is_super=True
        )
    
    if not is_admin(user_id):
        await message.answer("⛔ Sizda admin huquqi yo'q!")
        return
    
    await message.answer(
        "🚕 **Taxi Bot Admin Panel**\n\n"
        "Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery, state: FSMContext):
    """Asosiy menu"""
    await state.clear()
    await safe_edit_text(
        callback.message,
        "🚕 **Taxi Bot Admin Panel**\n\n"
        "Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Bekor qilish"""
    await state.clear()
    await safe_edit_text(
        callback.message,
        "❌ Bekor qilindi",
        reply_markup=back_keyboard()
    )


@router.callback_query(F.data == "noop")
async def noop_action(callback: CallbackQuery):
    """Hech narsa qilmaydigan callback"""
    await callback.answer()


# ============== GROUPS HANDLERS ==============

@router.callback_query(F.data == "groups_menu")
async def groups_menu(callback: CallbackQuery):
    """Guruhlar menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    
    groups = db.get_source_groups()
    active = len([g for g in groups if g['is_active']])
    
    await safe_edit_text(
        callback.message,
        f"📋 **Guruhlar boshqaruvi**\n\n"
        f"Jami guruhlar: {len(groups)}\n"
        f"Faol: {active}",
        reply_markup=groups_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "add_group")
async def add_group_start(callback: CallbackQuery, state: FSMContext):
    """Guruh qo'shish boshlash"""
    await state.set_state(AddGroupState.waiting_for_group)
    await safe_edit_text(
        callback.message,
        "📋 **Guruh qo'shish**\n\n"
        "Botni guruhga qo'shing va guruh ID'sini yuboring.\n\n"
        "ID topish: guruhdan xabarni @userinfobot ga forward qiling",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )


@router.message(AddGroupState.waiting_for_group)
async def add_group_finish(message: Message, state: FSMContext):
    """Guruh qo'shish yakunlash"""
    try:
        # Textni olish va bo'lish (yangi qator, vergul yoki bo'sh joy)
        raw_text = message.text.replace(",", "\n").replace(" ", "\n")
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        
        added_count = 0
        errors = []
        
        for line in lines:
            try:
                group_id = int(line)
                
                # Guruh qo'shish
                success = db.add_source_group(
                    group_id=group_id,
                    title=f"Guruh {group_id}",
                    added_by=message.from_user.id
                )
                if success:
                    added_count += 1
                else:
                    errors.append(f"{group_id} (balki mavjuddir)")
            except ValueError:
                errors.append(f"{line} (noto'g'ri ID)")
        
        response = f"✅ Jami {added_count} ta guruh qo'shildi!\n"
        if errors:
            response += f"\n⚠️ Xatolar:\n" + "\n".join(errors[:5])
        
        await message.answer(
            response,
            reply_markup=back_keyboard("groups_menu"),
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        await message.answer(
            f"❌ Xatolik yuz berdi: {e}",
            reply_markup=cancel_keyboard()
        )


@router.callback_query(F.data == "list_groups")
async def list_groups(callback: CallbackQuery, state: FSMContext):
    """Guruhlar ro'yxati (pagination bilan)"""
    groups = db.get_source_groups()
    
    if not groups:
        await safe_edit_text(
            callback.message,
            "📋 Guruhlar ro'yxati bo'sh",
            reply_markup=back_keyboard("groups_menu")
        )
        return
    
    # Birinchi sahifa
    page = 0
    await show_groups_page(callback, groups, page, state)


async def show_groups_page(callback: CallbackQuery, groups: list, page: int, state: FSMContext):
    """Guruhlarni sahifa bo'yicha ko'rsatish"""
    
    items_per_page = 10
    total_pages = (len(groups) + items_per_page - 1) // items_per_page
    
    # Sahifa chegarasini tekshirish
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    # Sahifadagi guruhlar
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_groups = groups[start_idx:end_idx]
    
    # Matn
    text = f"📋 **Guruhlar ro'yxati** ({len(groups)} ta)\n\n"
    text += f"Sahifa: {page + 1}/{total_pages}\n\n"
    
    buttons = []
    
    for g in page_groups:
        status = "🟢" if g['is_active'] else "🔴"
        text += f"{status} `{g['group_id']}` - {g['title'] or 'Nomsiz'}\n"
        buttons.append([
            InlineKeyboardButton(
                text=f"{'🔴 Ochir' if g['is_active'] else '🟢 Yoq'}: {g['group_id']}",
                callback_data=f"toggle_group:{g['group_id']}"
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"delete_group:{g['group_id']}"
            )
        ])
    
    # Pagination tugmalari
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"groups_page:{page - 1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"groups_page:{page + 1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="groups_menu")])
    
    # State'ga sahifani saqlash
    await state.update_data(groups_page=page, groups_list=groups)
    
    await safe_edit_text(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("groups_page:"))
async def groups_page_handler(callback: CallbackQuery, state: FSMContext):
    """Guruhlar sahifasini o'zgartirish"""
    page = int(callback.data.split(":")[1])
    groups = db.get_source_groups()
    await show_groups_page(callback, groups, page, state)


@router.callback_query(F.data.startswith("toggle_group:"))
async def toggle_group(callback: CallbackQuery, state: FSMContext):
    """Guruhni yoqish/o'chirish"""
    group_id = int(callback.data.split(":")[1])
    db.toggle_source_group(group_id)
    await callback.answer("✅ O'zgartirildi")
    
    # Sahifani qayta ko'rsatish
    groups = db.get_source_groups()
    data = await state.get_data()
    page = data.get('groups_page', 0)
    await show_groups_page(callback, groups, page, state)


@router.callback_query(F.data.startswith("delete_group:"))
async def delete_group(callback: CallbackQuery, state: FSMContext):
    """Guruhni o'chirish"""
    group_id = int(callback.data.split(":")[1])
    db.remove_source_group(group_id)
    await callback.answer("🗑 O'chirildi")
    
    # Sahifani qayta ko'rsatish
    groups = db.get_source_groups()
    data = await state.get_data()
    page = data.get('groups_page', 0)
    await show_groups_page(callback, groups, page, state)


# ============== TARGET GROUP HANDLERS ==============

@router.callback_query(F.data == "target_menu")
async def target_menu(callback: CallbackQuery):
    """Buyurtmalar guruhlari menusi"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    
    target_groups = db.get_target_groups()
    
    text = f"📤 **Buyurtmalar guruhlari**\n\n"
    if target_groups:
        text += f"Jami: {len(target_groups)}\n\n"
        for tg in target_groups:
            text += f"`{tg}`\n"
    else:
        text += "⚠️ Hali sozlanmagan"
    
    buttons = []
    
    # Guruhlar ro'yxati va o'chirish
    for tg in target_groups:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {tg} ni o'chirish", callback_data=f"del_target:{tg}")
        ])
    
    buttons.append([InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data="add_target")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")])
    
    await safe_edit_text(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "add_target")
async def add_target_start(callback: CallbackQuery, state: FSMContext):
    """Target guruh qo'shish"""
    await state.set_state(SetTargetState.waiting_for_group)
    await safe_edit_text(
        callback.message,
        "📤 **Buyurtmalar guruhini qo'shish**\n\n"
        "Guruh ID'sini yuboring:",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )


@router.message(SetTargetState.waiting_for_group)
async def add_target_finish(message: Message, state: FSMContext):
    """Target guruh yakunlash"""
    try:
        group_id = int(message.text.strip())
        db.add_target_group(group_id)
        
        await message.answer(
            f"✅ Buyurtmalar guruhi qo'shildi!\n\nID: `{group_id}`",
            reply_markup=back_keyboard("target_menu"),
            parse_mode="Markdown"
        )
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format!",
            reply_markup=cancel_keyboard()
        )


@router.callback_query(F.data.startswith("del_target:"))
async def delete_target(callback: CallbackQuery):
    """Target guruhni o'chirish"""
    try:
        group_id = int(callback.data.split(":")[1])
        db.remove_target_group(group_id)
        await callback.answer("✅ O'chirildi")
        await target_menu(callback)
    except Exception as e:
        await callback.answer("❌ Xatolik", show_alert=True)


# ============== ADMINS HANDLERS ==============

@router.callback_query(F.data == "admins_menu")
async def admins_menu(callback: CallbackQuery):
    """Adminlar menu"""
    if not db.is_super_admin(callback.from_user.id) and callback.from_user.id not in Config.SUPER_ADMIN_IDS:
        await callback.answer("⛔ Faqat super admin!", show_alert=True)
        return
    
    admins = db.get_all_admins()
    await safe_edit_text(
        callback.message,
        f"👥 **Adminlar boshqaruvi**\n\nJami: {len(admins)}",
        reply_markup=admins_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "add_admin")
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    """Admin qo'shish"""
    if not db.is_super_admin(callback.from_user.id) and callback.from_user.id not in Config.SUPER_ADMIN_IDS:
        await callback.answer("⛔ Faqat super admin!", show_alert=True)
        return
    
    await state.set_state(AddAdminState.waiting_for_user)
    await safe_edit_text(
        callback.message,
        "👥 **Admin qo'shish**\n\n"
        "Foydalanuvchi ID'sini yuboring yoki\n"
        "xabarini forward qiling:",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )


@router.message(AddAdminState.waiting_for_user)
async def add_admin_finish(message: Message, state: FSMContext):
    """Admin qo'shish yakunlash"""
    try:
        # Forward qilingan xabar
        if message.forward_from:
            user = message.forward_from
            user_id = user.id
            username = user.username
            full_name = user.full_name
        else:
            user_id = int(message.text.strip())
            username = None
            full_name = None
        
        success = db.add_admin(user_id, username, full_name)
        
        if success:
            await message.answer(
                f"✅ Admin qo'shildi!\n\nID: `{user_id}`",
                reply_markup=back_keyboard("admins_menu"),
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Xatolik!", reply_markup=back_keyboard("admins_menu"))
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format!", reply_markup=cancel_keyboard())


@router.callback_query(F.data == "list_admins")
async def list_admins(callback: CallbackQuery):
    """Adminlar ro'yxati"""
    admins = db.get_all_admins()
    
    if not admins:
        await safe_edit_text(
            callback.message,
            "👥 Adminlar ro'yxati bo'sh",
            reply_markup=back_keyboard("admins_menu")
        )
        return
    
    text = "👥 **Adminlar ro'yxati:**\n\n"
    buttons = []
    
    for a in admins:
        role = "👑" if a['is_super_admin'] else "👤"
        name = a['full_name'] or a['username'] or str(a['user_id'])
        text += f"{role} `{a['user_id']}` - {name}\n"
        
        if not a['is_super_admin']:
            buttons.append([
                InlineKeyboardButton(
                    text=f"🗑 {name}",
                    callback_data=f"delete_admin:{a['user_id']}"
                )
            ])
    
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admins_menu")])
    
    await safe_edit_text(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("delete_admin:"))
async def delete_admin(callback: CallbackQuery):
    """Adminni o'chirish"""
    user_id = int(callback.data.split(":")[1])
    db.remove_admin(user_id)
    await callback.answer("🗑 O'chirildi")
    await list_admins(callback)


# ============== STATS HANDLERS ==============

@router.callback_query(F.data == "stats")
async def show_stats(callback: CallbackQuery):
    """Statistika"""
    today = db.get_today_stats()
    total = db.get_total_stats()
    groups = len(db.get_source_groups())
    active_groups = len(db.get_active_group_ids())
    target_groups = len(db.get_target_groups())
    monitored_groups = len(db.get_monitored_groups())
    
    text = (
        "📊 **Statistika**\n\n"
        f"**Bugun:**\n"
        f"├ Qayta ishlangan: {today['processed']}\n"
        f"├ Yuborilgan: {today['forwarded']}\n"
        f"└ Filtrlangan: {today['filtered']}\n\n"
        f"**Umumiy:**\n"
        f"├ Qayta ishlangan: {total['processed']}\n"
        f"├ Yuborilgan: {total['forwarded']}\n"
        f"└ Filtrlangan: {total['filtered']}\n\n"
        f"**Guruhlar:**\n"
        f"├ Kuzatiladigan: {active_groups}/{groups} faol\n"
        f"├ Buyurtmalar: {target_groups}\n"
        f"└ Qo'shimcha: {monitored_groups}"
    )
    
    await safe_edit_text(
        callback.message,
        text,
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )


# ============== AI SETTINGS HANDLERS ==============

@router.callback_query(F.data == "ai_menu")
async def ai_menu(callback: CallbackQuery):
    """AI sozlamalari menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    
    current_prompt = db.get_setting("ai_prompt")
    status = "✅ Maxsus prompt" if current_prompt else "📝 Default prompt"
    
    buttons = [
        [InlineKeyboardButton(text="👁 Promptni ko'rish", callback_data="view_prompt")],
        [InlineKeyboardButton(text="✏️ Promptni o'zgartirish", callback_data="edit_prompt")],
        [InlineKeyboardButton(text="🔄 Defaultga qaytarish", callback_data="reset_prompt")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")],
    ]
    
    await safe_edit_text(
        callback.message,
        f"🤖 **AI Sozlamalari**\n\n"
        f"Holat: {status}\n\n"
        f"AI prompt - xabarlarni tahlil qilish uchun ishlatiladi.\n"
        f"Yo'lovchi va haydovchi zakazlarini ajratadi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "view_prompt")
async def view_prompt(callback: CallbackQuery):
    """Promptni ko'rish"""
    from ai_classifier import DEFAULT_PROMPT
    
    current_prompt = db.get_setting("ai_prompt") or DEFAULT_PROMPT
    
    # Telegram limit - 4096 characters
    if len(current_prompt) > 3500:
        current_prompt = current_prompt[:3500] + "\n\n... (qisqartirildi)"
    
    await safe_edit_text(
        callback.message,
        f"🤖 **Joriy AI Prompt:**\n\n```\n{current_prompt}\n```",
        reply_markup=back_keyboard("ai_menu"),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "edit_prompt")
async def edit_prompt_start(callback: CallbackQuery, state: FSMContext):
    """Prompt o'zgartirish"""
    await state.set_state(AIPromptState.waiting_for_prompt)
    await safe_edit_text(
        callback.message,
        "✏️ **AI Promptni o'zgartirish**\n\n"
        "Yangi promptni yuboring.\n\n"
        "Prompt JSON formatda javob qaytarishi kerak:\n"
        "- `type`: passenger_order | driver_order | other\n"
        "- `confidence`: 0.0-1.0\n"
        "- `data`: {from_location, to_location, phone, ...}",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )


@router.message(AIPromptState.waiting_for_prompt)
async def edit_prompt_finish(message: Message, state: FSMContext):
    """Prompt saqlash"""
    new_prompt = message.text.strip()
    
    if len(new_prompt) < 50:
        await message.answer(
            "❌ Prompt juda qisqa! Kamida 50 ta belgi bo'lishi kerak.",
            reply_markup=cancel_keyboard()
        )
        return
    
    db.set_setting("ai_prompt", new_prompt)
    
    await message.answer(
        "✅ AI prompt saqlandi!\n\n"
        "Yangi prompt keyingi xabarlardan boshlab ishlatiladi.",
        reply_markup=back_keyboard("ai_menu"),
        parse_mode="Markdown"
    )
    await state.clear()


@router.callback_query(F.data == "reset_prompt")
async def reset_prompt(callback: CallbackQuery):
    """Promptni default ga qaytarish"""
    db.set_setting("ai_prompt", "")
    await callback.answer("✅ Default promptga qaytarildi")
    await ai_menu(callback)


# ============== BLOCK USER HANDLER ==============

@router.callback_query(F.data.startswith("block_user:"))
async def handle_block_user(callback: CallbackQuery):
    """Foydalanuvchini bloklash"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[1])
    
    # Bloklash
    if db.block_user(user_id, blocked_by=callback.from_user.id):
        await callback.answer(f"🚫 Foydalanuvchi {user_id} bloklandi!", show_alert=True)
        
        # Tugmani o'zgartirish
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Bloklangan", callback_data=f"unblock_user:{user_id}")]
            ])
        )
    else:
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("unblock_user:"))
async def handle_unblock_user(callback: CallbackQuery):
    """Foydalanuvchini blokdan chiqarish"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[1])
    
    # Blokdan chiqarish
    if db.unblock_user(user_id):
        await callback.answer(f"✅ Foydalanuvchi {user_id} blokdan chiqarildi!", show_alert=True)
        
        # Tugmani o'zgartirish
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚫 Bloklash", callback_data=f"block_user:{user_id}")]
            ])
        )
    else:
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)


# ============== KEYWORDS HANDLERS ==============

@router.callback_query(F.data == "keywords_menu")
async def keywords_menu(callback: CallbackQuery):
    """Kalit so'zlar menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    await safe_edit_text(
        callback.message,
        "🔑 **Kalit so'zlar bo'limi**\n\n"
        "Tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Haydovchi so'zlari (IGNORE)", callback_data="kw_list:driver")],
            [InlineKeyboardButton(text="✅ Yo'lovchi so'zlari (FORCE)", callback_data="kw_list:passenger")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
        ]),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("kw_list:"))
async def keywords_list(callback: CallbackQuery, state: FSMContext):
    """Kalit so'zlar ro'yxati"""
    parts = callback.data.split(":")
    ktype = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0
    
    name = "Haydovchi" if ktype == 'driver' else "Yo'lovchi"
    
    keywords = db.get_keywords(ktype)
    
    # Pagination
    items_per_page = 10
    total_pages = (len(keywords) + items_per_page - 1) // items_per_page if keywords else 1
    
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_keywords = keywords[start_idx:end_idx]
    
    text = f"🔑 **{name} so'zlari**\n\n"
    if not keywords:
        text += "❌ Hozircha so'zlar yo'q"
    else:
        text += f"Sahifa: {page + 1}/{total_pages}\n\n"
        for k in page_keywords:
            text += f"▫️ `{k['word']}`\n"
    
    text += "\n👇 Qo'shish yoki o'chirish uchun tanlang:"
    
    # Tugmalar (har bir so'z uchun o'chirish tugmasi)
    buttons = []
    
    for k in page_keywords:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {k['word']}", callback_data=f"kw_del:{k['id']}:{ktype}:{page}")
        ])
    
    # Pagination tugmalari
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"kw_list:{ktype}:{page - 1}"))
    
    if len(keywords) > 0:
        nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"kw_list:{ktype}:{page + 1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="➕ Yangi so'z qo'shish", callback_data=f"kw_add:{ktype}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="keywords_menu")])
    
    await state.update_data(kw_page=page, kw_type=ktype)
    
    await safe_edit_text(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("kw_add:"))
async def keyword_add_start(callback: CallbackQuery, state: FSMContext):
    """Kalit so'z qo'shishni boshlash"""
    ktype = callback.data.split(":")[1]
    name = "haydovchi" if ktype == 'driver' else "yo'lovchi"
    
    await state.update_data(kw_type=ktype)
    await state.set_state(AddKeywordState.waiting_for_word)
    
    await safe_edit_text(
        callback.message,
        f"✍️ Yangi **{name}** so'zini kiriting:\n\n"
        "Masalan: `taxi kerak` yoki `bo'shman`\n"
        "Bekor qilish uchun /cancel yozing",
        parse_mode="Markdown"
    )


@router.message(AddKeywordState.waiting_for_word)
async def keyword_add_finish(message: Message, state: FSMContext):
    """Kalit so'zni saqlash"""
    data = await state.get_data()
    ktype = data.get('kw_type')
    text = message.text.strip()
    
    # Vergul bilan ajratilgan so'zlarni qabul qilish
    words = [w.strip() for w in text.split(',') if w.strip()]
    
    added_count = 0
    errors = []
    
    for word in words:
        if db.add_keyword(word, ktype, message.from_user.id):
            added_count += 1
        else:
            errors.append(word)
    
    # Natija
    if added_count > 0:
        await message.answer(f"✅ {added_count} ta kalit so'z qo'shildi!", parse_mode="Markdown")
    
    if errors:
        await message.answer(f"⚠️ Qo'shilmadi (mavjud): {', '.join(errors[:5])}", parse_mode="Markdown")
    
    await state.clear()
    
    # Menyuga qaytish
    name = "Haydovchi" if ktype == 'driver' else "Yo'lovchi"
    keywords = db.get_keywords(ktype)
    
    # Pagination
    items_per_page = 10
    total_pages = (len(keywords) + items_per_page - 1) // items_per_page if keywords else 1
    page = 0  # Birinchi sahifa
    
    page_keywords = keywords[:items_per_page]
    
    text = f"🔑 **{name} so'zlari**\n\n"
    if not keywords:
        text += "❌ Hozircha so'zlar yo'q"
    else:
        text += f"Sahifa: {page + 1}/{total_pages}\n\n"
        for k in page_keywords:
            text += f"▫️ `{k['word']}`\n"
    
    text += "\n👇 Qo'shish yoki o'chirish uchun tanlang:"
    
    # Tugmalar
    buttons = []
    for k in page_keywords:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {k['word']}", callback_data=f"kw_del:{k['id']}:{ktype}:{page}")
        ])
    
    # Pagination tugmalari
    nav_buttons = []
    if len(keywords) > items_per_page:
        nav_buttons.append(InlineKeyboardButton(text=f"📄 1/{total_pages}", callback_data="noop"))
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"kw_list:{ktype}:1"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="➕ Yangi so'z qo'shish", callback_data=f"kw_add:{ktype}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="keywords_menu")])
    
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("kw_del:"))
async def keyword_delete(callback: CallbackQuery, state: FSMContext):
    """Kalit so'zni o'chirish"""
    parts = callback.data.split(":")
    kw_id = int(parts[1])
    ktype = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0
    
    if db.remove_keyword(kw_id):
        await callback.answer("✅ O'chirildi")
        # Sahifani qayta ko'rsatish
        callback.data = f"kw_list:{ktype}:{page}"
        await keywords_list(callback, state)
    else:
        await callback.answer("❌ Xatolik", show_alert=True)


# ============== MONITORED GROUPS HANDLERS ==============

@router.callback_query(F.data == "monitored_menu")
async def monitored_menu(callback: CallbackQuery):
    """Qo'shimcha kuzatilayotgan guruhlar menusi"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    
    monitored_groups = db.get_monitored_groups()
    
    text = f"👁️ **Qo'shimcha kuzatilayotgan guruhlar**\n\n"
    if monitored_groups:
        text += f"Jami: {len(monitored_groups)}\n\n"
        for mg in monitored_groups:
            text += f"`{mg}`\n"
    else:
        text += "⚠️ Hali qo'shimcha guruh yo'q"
    
    buttons = []
    
    # Guruhlar ro'yxati va o'chirish
    for mg in monitored_groups:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {mg} ni o'chirish", callback_data=f"del_monitored:{mg}")
        ])
    
    buttons.append([InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data="add_monitored")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")])
    
    await safe_edit_text(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "add_monitored")
async def add_monitored_start(callback: CallbackQuery, state: FSMContext):
    """Qo'shimcha kuzatilayotgan guruh qo'shish"""
    await state.set_state(AddMonitoredGroupState.waiting_for_group)
    await safe_edit_text(
        callback.message,
        "👁️ **Qo'shimcha kuzatilayotgan guruh qo'shish**\n\n"
        "Guruh ID'sini yuboring:\n\n"
        "ID topish: guruhdan xabarni @userinfobot ga forward qiling",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )


@router.message(AddMonitoredGroupState.waiting_for_group)
async def add_monitored_finish(message: Message, state: FSMContext):
    """Qo'shimcha kuzatilayotgan guruh yakunlash"""
    try:
        # Textni olish va bo'lish (yangi qator, vergul yoki bo'sh joy)
        raw_text = message.text.replace(",", "\n").replace(" ", "\n")
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        
        added_count = 0
        errors = []
        
        for line in lines:
            try:
                group_id = int(line)
                
                # Guruh qo'shish
                success = db.add_monitored_group(group_id)
                if success:
                    added_count += 1
                else:
                    errors.append(f"{group_id} (balki mavjuddir)")
            except ValueError:
                errors.append(f"{line} (noto'g'ri ID)")
        
        response = f"✅ Jami {added_count} ta guruh qo'shildi!\n"
        if errors:
            response += f"\n⚠️ Xatolar:\n" + "\n".join(errors[:5])
        
        await message.answer(
            response,
            reply_markup=back_keyboard("monitored_menu"),
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        await message.answer(
            f"❌ Xatolik yuz berdi: {e}",
            reply_markup=cancel_keyboard()
        )


@router.callback_query(F.data.startswith("del_monitored:"))
async def delete_monitored(callback: CallbackQuery):
    """Qo'shimcha kuzatilayotgan guruhni o'chirish"""
    try:
        group_id = int(callback.data.split(":")[1])
        db.remove_monitored_group(group_id)
        await callback.answer("✅ O'chirildi")
        await monitored_menu(callback)
    except Exception as e:
        await callback.answer("❌ Xatolik", show_alert=True)
