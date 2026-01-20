import os
import json
import logging
from aiohttp import web
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import asyncio

from database import (
    init_db, get_all_products, get_product, add_product,
    delete_product, add_order, get_recent_orders, save_user
)

# =======================
# ENV + LOGGING
# =======================
load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://driphype-api.onrender.com
WEBAPP_URL = os.getenv("WEBAPP_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", 8000))

# =======================
# BOT INIT
# =======================
bot = Bot(BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# =======================
# FSM
# =======================
class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    image_url = State()
    category = State()
    product_type = State()
    sizes = State()

class DeleteProduct(StatesGroup):
    confirm = State()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# =======================
# KEYBOARDS
# =======================
def get_main_keyboard(is_admin_user: bool = False):
    """Постійна клавіатура внизу екрану"""
    keyboard = [
        [KeyboardButton(text="🛍️ Магазин", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton(text="ℹ️ Інформація")]
    ]
    
    if is_admin_user:
        keyboard.append([KeyboardButton(text="⚙️ Адмін")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Оберіть дію..."
    )

def get_admin_keyboard():
    """Inline кнопки для адмін панелі"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Додати", callback_data="add_product"),
            InlineKeyboardButton(text="📦 Товари", callback_data="list_products")
        ],
        [
            InlineKeyboardButton(text="🗑️ Видалити", callback_data="delete_product_menu"),
            InlineKeyboardButton(text="📊 Замовлення", callback_data="list_orders")
        ]
    ])

def get_category_keyboard():
    """Вибір категорії товару"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨 Чоловіче", callback_data="cat_чоловіче"),
            InlineKeyboardButton(text="👩 Жіноче", callback_data="cat_жіноче")
        ],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add")]
    ])

def get_product_type_keyboard():
    """Вибір типу товару"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👕 Одяг", callback_data="type_одяг"),
            InlineKeyboardButton(text="👟 Взуття", callback_data="type_взуття")
        ],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add")]
    ])

def get_cancel_keyboard():
    """Кнопка скасування"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add")]
    ])

# =======================
# START & MAIN MENU
# =======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    save_user(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
        1 if is_admin(user_id) else 0
    )

    welcome_text = (
        f"👋 <b>Вітаємо, {message.from_user.first_name}!</b>\n\n"
        "🎨 <b>DripHype</b> — ваш магазин стильного одягу\n\n"
        "💫 Відкрийте магазин щоб переглянути колекцію\n"
        "🚀 Швидке оформлення та зручна оплата\n\n"
        "Використовуйте кнопки внизу для навігації 👇"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(is_admin(user_id)),
        parse_mode="HTML"
    )

# =======================
# HANDLE KEYBOARD BUTTONS
# =======================
@dp.message(F.text == "ℹ️ Інформація")
async def show_info(message: types.Message):
    # Створюємо кнопки з посиланнями
    contact_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Власник", url="https://t.me/soryuko")],
        [InlineKeyboardButton(text="🤝 Співпраця", url="https://t.me/whytodie")]
    ])
    
    info_text = (
        "ℹ️ <b>Про DripHype</b>\n\n"
        "🎯 <b>Якість та стиль</b>\n"
        "Ми пропонуємо тільки найкращі речі\n\n"
        "🚚 <b>Швидка доставка</b>\n"
        "Доставка по всій Європі\n\n"
        "💳 <b>Зручна оплата</b>\n"
        "Безпечні методи оплати\n\n"
        "📞 <b>Підтримка</b>\n"
        "Натисніть на кнопки нижче для зв'язку"
    )
    
    await message.answer(info_text, reply_markup=contact_keyboard, parse_mode="HTML")

@dp.message(F.text == "⚙️ Адмін")
async def admin_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Доступ заборонено")

    admin_text = (
        "⚙️ <b>Панель адміністратора</b>\n\n"
        "Оберіть потрібну дію:"
    )
    
    await message.answer(
        admin_text,
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )

# =======================
# ADMIN PANEL CALLBACKS
# =======================
@dp.callback_query(F.data == "admin")
async def admin_panel_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("❌ Немає доступу", show_alert=True)

    admin_text = (
        "⚙️ <b>Панель адміністратора</b>\n\n"
        "Оберіть потрібну дію:"
    )

    await callback.message.edit_text(
        admin_text,
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# =======================
# ADD PRODUCT FLOW
# =======================
@dp.callback_query(F.data == "add_product")
async def start_add_product(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("❌ Немає доступу", show_alert=True)

    await state.set_state(AddProduct.name)
    await callback.message.edit_text(
        "📝 <b>Додавання товару</b>\n\n"
        "Крок 1/5: Введіть назву товару",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(AddProduct.name)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.description)
    await message.answer(
        "📝 <b>Додавання товару</b>\n\n"
        "Крок 2/5: Введіть опис товару",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )

@dp.message(AddProduct.description)
async def add_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProduct.price)
    await message.answer(
        "💰 <b>Додавання товару</b>\n\n"
        "Крок 3/5: Введіть ціну (тільки число)",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )

@dp.message(AddProduct.price)
async def add_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)
        await state.set_state(AddProduct.image_url)
        await message.answer(
            "🖼️ <b>Додавання товару</b>\n\n"
            "Крок 4/5: Надішліть URL зображення",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "❌ <b>Помилка!</b>\n\n"
            "Будь ласка, введіть коректне число",
            parse_mode="HTML"
        )

@dp.message(AddProduct.image_url)
async def add_image(message: types.Message, state: FSMContext):
    await state.update_data(image_url=message.text)
    await state.set_state(AddProduct.category)
    await message.answer(
        "📁 <b>Додавання товару</b>\n\n"
        "Крок 5/5: Оберіть категорію",
        reply_markup=get_category_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("cat_"))
async def add_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("cat_", "")
    await state.update_data(category=category)
    await state.set_state(AddProduct.product_type)
    await callback.message.edit_text(
        "🏷️ <b>Тип товару</b>\n\n"
        "Оберіть тип товару:",
        reply_markup=get_product_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("type_"))
async def add_product_type(callback: types.CallbackQuery, state: FSMContext):
    product_type = callback.data.replace("type_", "")
    await state.update_data(product_type=product_type)
    await state.set_state(AddProduct.sizes)
    
    if product_type == "взуття":
        size_example = "<i>Приклад: 36, 37, 38, 39, 40</i>"
    else:
        size_example = "<i>Приклад: S, M, L, XL</i>"
    
    await callback.message.edit_text(
        "📏 <b>Останній крок!</b>\n\n"
        f"Введіть доступні розміри через кому\n"
        f"{size_example}",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(AddProduct.sizes)
async def finish_product(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    try:
        product_id = add_product(
            data["name"], 
            data["description"], 
            data["price"],
            data["image_url"], 
            data["category"], 
            data.get("product_type", "одяг"),  # Використовуємо збережений тип
            message.text
        )
        
        success_text = (
            "✅ <b>Товар успішно додано!</b>\n\n"
            f"🆔 ID: #{product_id}\n"
            f"📦 Назва: {data['name']}\n"
            f"💰 Ціна: {data['price']} грн\n"
            f"📁 Категорія: {data['category']}\n"
            f"🏷️ Тип: {data.get('product_type', 'одяг')}\n"
            f"📏 Розміри: {message.text}"
        )
        
        await message.answer(success_text, parse_mode="HTML")
        await state.clear()
        
    except Exception as e:
        logging.error(f"Error adding product: {e}")
        await message.answer(
            "❌ <b>Помилка при додаванні товару</b>\n\n"
            "Спробуйте ще раз",
            parse_mode="HTML"
        )
        await state.clear()

@dp.callback_query(F.data == "cancel_add")
async def cancel_add_product(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Додавання скасовано</b>",
        parse_mode="HTML"
    )
    await callback.answer()

# =======================
# WEB APP ORDERS
# =======================
@dp.message(F.content_type == types.ContentType.WEB_APP_DATA)
async def web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        order_id = add_order(
            message.from_user.id,
            message.from_user.username,
            json.dumps(data["products"]),
            data["total"]
        )
        
        order_text = (
            "✅ <b>Замовлення прийнято!</b>\n\n"
            f"🆔 Номер: #{order_id}\n"
            f"💰 Сума: {data['total']} грн\n\n"
            "📞 Ми зв'яжемося з вами найближчим часом!"
        )
        
        await message.answer(order_text, parse_mode="HTML")
        
    except Exception as e:
        logging.error(f"Error processing order: {e}")
        await message.answer(
            "❌ <b>Помилка при оформленні замовлення</b>\n\n"
            "Спробуйте ще раз або зв'яжіться з підтримкою",
            parse_mode="HTML"
        )

# =======================
# LIST PRODUCTS
# =======================
@dp.callback_query(F.data == "list_products")
async def list_products_handler(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("❌ Немає доступу", show_alert=True)
    
    try:
        products = get_all_products()
        
        if not products:
            await callback.message.edit_text(
                "📦 <b>Список товарів порожній</b>",
                reply_markup=get_admin_keyboard(),
                parse_mode="HTML"
            )
            return await callback.answer()
        
        products_text = "📦 <b>Список товарів:</b>\n\n"
        for p in products[:15]:  # Показуємо перші 15
            # Перевіряємо чи це словник чи кортеж
            if isinstance(p, dict):
                product_id = p.get('id', 'N/A')
                name = p.get('name', 'N/A')
                price = p.get('price', 0)
                category = p.get('category', 'N/A')
                product_type = p.get('product_type', 'одяг')
                sizes = p.get('sizes', 'N/A')
            else:
                product_id = p[0] if len(p) > 0 else 'N/A'
                name = p[1] if len(p) > 1 else 'N/A'
                price = p[3] if len(p) > 3 else 0
                category = p[5] if len(p) > 5 else 'N/A'
                product_type = p[6] if len(p) > 6 else 'одяг'
                sizes = p[7] if len(p) > 7 else 'N/A'
            
            product_type_emoji = "👟" if product_type == "взуття" else "👕"
            products_text += (
                f"{product_type_emoji} <b>{name}</b>\n"
                f"🆔 ID: #{product_id} | 💰 {price} грн\n"
                f"📁 {category} | 📏 {sizes}\n\n"
            )
        
        if len(products) > 15:
            products_text += f"\n<i>... та ще {len(products) - 15} товарів</i>"
        
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
        ])
        
        await callback.message.edit_text(
            products_text,
            reply_markup=back_keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error listing products: {e}")
        await callback.answer("❌ Помилка при завантаженні товарів", show_alert=True)

# =======================
# DELETE PRODUCT
# =======================
@dp.callback_query(F.data == "delete_product_menu")
async def delete_product_menu_handler(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("❌ Немає доступу", show_alert=True)
    
    try:
        products = get_all_products()
        
        if not products:
            await callback.message.edit_text(
                "📦 <b>Немає товарів для видалення</b>",
                reply_markup=get_admin_keyboard(),
                parse_mode="HTML"
            )
            return await callback.answer()
        
        # Створюємо кнопки для кожного товару
        keyboard_buttons = []
        for p in products[:20]:  # Показуємо до 20 товарів
            if isinstance(p, dict):
                product_id = p.get('id', 0)
                name = p.get('name', 'N/A')
                product_type = p.get('product_type', 'одяг')
            else:
                product_id = p[0] if len(p) > 0 else 0
                name = p[1] if len(p) > 1 else 'N/A'
                product_type = p[6] if len(p) > 6 else 'одяг'
            
            product_type_emoji = "👟" if product_type == "взуття" else "👕"
            button_text = f"{product_type_emoji} {name} (#{product_id})"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"delete_{product_id}"
                )
            ])
        
        # Додаємо кнопку назад
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin")
        ])
        
        delete_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(
            "🗑️ <b>Видалення товару</b>\n\n"
            "Оберіть товар для видалення:",
            reply_markup=delete_keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error showing delete menu: {e}")
        await callback.answer("❌ Помилка при завантаженні", show_alert=True)

@dp.callback_query(F.data.startswith("delete_"))
async def confirm_delete_product(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("❌ Немає доступу", show_alert=True)
    
    try:
        product_id = int(callback.data.replace("delete_", ""))
        product = get_product(product_id)
        
        if not product:
            await callback.answer("❌ Товар не знайдено", show_alert=True)
            return
        
        # Отримуємо дані товару
        if isinstance(product, dict):
            name = product.get('name', 'N/A')
            price = product.get('price', 0)
            category = product.get('category', 'N/A')
        else:
            name = product[1] if len(product) > 1 else 'N/A'
            price = product[3] if len(product) > 3 else 0
            category = product[5] if len(product) > 5 else 'N/A'
        
        # Створюємо клавіатуру підтвердження
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Так, видалити", callback_data=f"confirm_delete_{product_id}"),
                InlineKeyboardButton(text="❌ Скасувати", callback_data="delete_product_menu")
            ]
        ])
        
        await callback.message.edit_text(
            f"🗑️ <b>Підтвердження видалення</b>\n\n"
            f"📦 Товар: {name}\n"
            f"💰 Ціна: {price} грн\n"
            f"📁 Категорія: {category}\n\n"
            f"Ви впевнені, що хочете видалити цей товар?",
            reply_markup=confirm_keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error confirming delete: {e}")
        await callback.answer("❌ Помилка", show_alert=True)

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def delete_product_confirmed(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("❌ Немає доступу", show_alert=True)
    
    try:
        product_id = int(callback.data.replace("confirm_delete_", ""))
        delete_product(product_id)
        
        await callback.message.edit_text(
            f"✅ <b>Товар #{product_id} успішно видалено!</b>",
            parse_mode="HTML"
        )
        await callback.answer("✅ Видалено!")
        
        # Через 2 секунди повертаємо до адмін панелі
        import asyncio
        await asyncio.sleep(2)
        await callback.message.edit_text(
            "⚙️ <b>Панель адміністратора</b>\n\n"
            "Оберіть потрібну дію:",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Error deleting product: {e}")
        await callback.answer("❌ Помилка при видаленні", show_alert=True)

# =======================
# LIST ORDERS
# =======================
@dp.callback_query(F.data == "list_orders")
async def list_orders_handler(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("❌ Немає доступу", show_alert=True)
    
    try:
        orders = get_recent_orders(10)
        
        if not orders:
            await callback.message.edit_text(
                "📊 <b>Замовлень поки немає</b>",
                reply_markup=get_admin_keyboard(),
                parse_mode="HTML"
            )
            return await callback.answer()
        
        orders_text = "📊 <b>Останні замовлення:</b>\n\n"
        for o in orders:
            # Перевіряємо чи це словник чи кортеж
            if isinstance(o, dict):
                order_id = o.get('id', 'N/A')
                username = o.get('username', 'Unknown')
                total = o.get('total', 0)
                created_at = o.get('created_at', 'N/A')
            else:
                order_id = o[0] if len(o) > 0 else 'N/A'
                username = o[2] if len(o) > 2 else 'Unknown'
                total = o[4] if len(o) > 4 else 0
                created_at = o[5] if len(o) > 5 else 'N/A'
            
            orders_text += (
                f"🆔 #{order_id} | @{username or 'Unknown'}\n"
                f"💰 {total} грн\n"
                f"📅 {created_at}\n\n"
            )
        
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
        ])
        
        await callback.message.edit_text(
            orders_text,
            reply_markup=back_keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error listing orders: {e}")
        await callback.answer("❌ Помилка при завантаженні замовлень", show_alert=True)

# =======================
# WEBHOOK APP
# =======================

# Глобальна змінна для контролю фонового таску
background_tasks = set()

# Фоновий таск для автоматичної перевірки webhook
async def webhook_monitor():
    """Перевіряє та оновлює webhook кожні 3 хвилини"""
    logging.info("🔄 Webhook monitor запущено!")
    
    # Чекаємо 30 секунд після старту
    await asyncio.sleep(30)
    
    while True:
        try:
            webhook_info = await bot.get_webhook_info()
            expected_url = f"{WEBHOOK_URL}/webhook/bot"
            
            # Перевіряємо чи webhook встановлений правильно
            if not webhook_info.url or webhook_info.url != expected_url:
                logging.warning(f"⚠️ Webhook URL неправильний! Очікуємо: {expected_url}, Поточний: {webhook_info.url}")
                await bot.delete_webhook(drop_pending_updates=True)
                await asyncio.sleep(2)
                await bot.set_webhook(url=expected_url, drop_pending_updates=True)
                logging.info(f"✅ Webhook автоматично оновлено на {expected_url}")
                
            elif webhook_info.pending_update_count > 30:
                # Якщо накопичилось багато оновлень - перезапускаємо webhook
                logging.warning(f"⚠️ Багато pending updates: {webhook_info.pending_update_count}")
                await bot.delete_webhook(drop_pending_updates=True)
                await asyncio.sleep(2)
                await bot.set_webhook(url=expected_url, drop_pending_updates=True)
                logging.info("✅ Webhook автоматично перезапущено через pending updates")
                
            else:
                logging.info(f"✅ Webhook перевірено: OK (pending: {webhook_info.pending_update_count})")
            
        except asyncio.CancelledError:
            logging.info("🛑 Webhook monitor зупинено")
            break
        except Exception as e:
            logging.error(f"❌ Помилка в webhook monitor: {e}")
        
        # Перевіряємо кожні 3 хвилини (180 секунд)
        await asyncio.sleep(180)

async def on_startup(app: web.Application):
    """Виконується при старті додатку"""
    logging.info("🚀 Запуск бота...")
    
    # Ініціалізуємо базу даних
    init_db()
    
    webhook_url = f"{WEBHOOK_URL}/webhook/bot"
    
    try:
        # Отримуємо інфо про поточний webhook
        webhook_info = await bot.get_webhook_info()
        logging.info(f"📡 Поточний webhook: {webhook_info.url or 'НЕ ВСТАНОВЛЕНО'}")
        
        # Завжди видаляємо старий webhook при старті
        if webhook_info.url:
            await bot.delete_webhook(drop_pending_updates=True)
            logging.info("🗑️ Старий webhook видалено")
            await asyncio.sleep(2)  # Даємо час Telegram обробити
        
        # Встановлюємо новий webhook
        result = await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        
        if result:
            logging.info(f"✅ Webhook успішно встановлено на {webhook_url}")
        else:
            logging.error("❌ Не вдалось встановити webhook!")
        
        # Перевіряємо що встановилось
        await asyncio.sleep(1)
        new_webhook_info = await bot.get_webhook_info()
        logging.info(f"📋 Webhook статус: URL={new_webhook_info.url}, Pending={new_webhook_info.pending_update_count}")
        
        # Запускаємо фоновий моніторинг webhook
        task = asyncio.create_task(webhook_monitor())
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        
        logging.info("🔄 Автоматичний моніторинг webhook запущено (перевірка кожні 3 хвилини)")
        
    except Exception as e:
        logging.error(f"❌ Критична помилка при встановленні webhook: {e}", exc_info=True)

async def on_shutdown(app: web.Application):
    """Виконується при зупинці додатку"""
    logging.info("🛑 Зупинка бота...")
    
    # Скасовуємо всі фонові таски
    for task in background_tasks:
        task.cancel()
    
    # Чекаємо завершення всіх тасків
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)
    
    try:
        await bot.delete_webhook()
        await bot.session.close()
        logging.info("✅ Webhook видалено, сесія закрита")
    except Exception as e:
        logging.error(f"❌ Помилка при shutdown: {e}")

# Ендпоінт для API info (головна сторінка)
async def api_info(request):
    return web.json_response({
        "status": "online",
        "message": "Driphype Shop API is running",
        "mode": "webhook",
        "endpoints": {
            "/api/products": "GET - Отримати всі товари",
            "/api/products/{id}": "GET - Отримати товар за ID",
            "/webhook/bot": "POST - Telegram webhook",
            "/status": "GET - Bot status dashboard",
            "/update-webhook": "GET - Force update webhook"
        }
    })

# Ендпоінт для перевірки статусу (dashboard)
async def health_check(request):
    try:
        webhook_info = await bot.get_webhook_info()
        bot_info = await bot.get_me()
        
        # Перевіряємо чи працює моніторинг
        monitor_status = "🟢 Активний" if len(background_tasks) > 0 else "🔴 Не запущено"
        
        html = f"""
        <html>
        <head>
            <title>DripHype Bot Status</title>
            <meta http-equiv="refresh" content="10">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    padding: 40px;
                    background: linear-gradient(135deg, #1a1a1a 0%, #2d1b4e 100%);
                    color: #fff;
                    margin: 0;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: rgba(0, 0, 0, 0.5);
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 8px 32px rgba(168, 85, 247, 0.2);
                }}
                h1 {{
                    color: #a855f7;
                    margin-bottom: 30px;
                }}
                .status-item {{
                    background: rgba(255, 255, 255, 0.05);
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 8px;
                    border-left: 3px solid #a855f7;
                }}
                .status-item strong {{
                    color: #c084fc;
                }}
                .btn {{
                    display: inline-block;
                    color: #fff;
                    background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
                    text-decoration: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    margin-top: 20px;
                    transition: transform 0.2s;
                }}
                .btn:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(168, 85, 247, 0.4);
                }}
                .footer {{
                    text-align: center;
                    color: #888;
                    font-size: 12px;
                    margin-top: 30px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 DripHype Bot Dashboard</h1>
                
                <div class="status-item">
                    <strong>Bot Status:</strong> ✅ Running
                </div>
                
                <div class="status-item">
                    <strong>Bot Username:</strong> @{bot_info.username}
                </div>
                
                <div class="status-item">
                    <strong>Bot ID:</strong> {bot_info.id}
                </div>
                
                <div class="status-item">
                    <strong>Webhook URL:</strong> {webhook_info.url or '❌ НЕ ВСТАНОВЛЕНО'}
                </div>
                
                <div class="status-item">
                    <strong>Pending Updates:</strong> {webhook_info.pending_update_count}
                </div>
                
                <div class="status-item">
                    <strong>Auto Monitor:</strong> {monitor_status}
                </div>
                
                <div class="status-item">
                    <strong>Background Tasks:</strong> {len(background_tasks)}
                </div>
                
                <a href="/update-webhook" class="btn">🔄 Force Update Webhook</a>
                
                <div class="footer">
                    Сторінка автоматично оновлюється кожні 10 секунд
                </div>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    except Exception as e:
        return web.Response(text=f"Error: {str(e)}", status=500)

# Ендпоінт для форсованого оновлення webhook
async def force_update_webhook(request):
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
        
        webhook_url = f"{WEBHOOK_URL}/webhook/bot"
        result = await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "inline_query"]
        )
        
        webhook_info = await bot.get_webhook_info()
        
        html = f"""
        <html>
        <head>
            <title>Webhook Updated</title>
            <meta http-equiv="refresh" content="3;url=/">
        </head>
        <body style="font-family: Arial; padding: 20px; background: #1a1a1a; color: #fff;">
            <h1>{'✅ Webhook Updated!' if result else '❌ Update Failed'}</h1>
            <p><strong>Webhook URL:</strong> {webhook_info.url}</p>
            <p><strong>Pending Updates:</strong> {webhook_info.pending_update_count}</p>
            <p>Redirecting to home page in 3 seconds...</p>
            <p><a href="/" style="color: #4CAF50;">Go back now</a></p>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    except Exception as e:
        logging.error(f"Error updating webhook: {e}")
        return web.Response(text=f"Error: {str(e)}", status=500)

app = web.Application()

# Додаємо startup/shutdown
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# Додаємо наші роути СПОЧАТКУ
app.router.add_get('/', api_info)
app.router.add_get('/status', health_check)
app.router.add_get('/health', health_check)
app.router.add_get('/update-webhook', force_update_webhook)
app.router.add_post('/update-webhook', force_update_webhook)

# Реєструємо webhook handler (це додає роут /webhook/bot)
webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
webhook_handler.register(app, path="/webhook/bot")

# НЕ використовуємо setup_application, бо він перезаписує роути
# setup_application(app, dp, bot=bot)  # <-- Закоментовано

if __name__ == "__main__":
    web.run_app(app, port=PORT)
