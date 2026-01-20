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
    info_text = (
        "ℹ️ <b>Про DripHype</b>\n\n"
        "🎯 <b>Якість та стиль</b>\n"
        "Ми пропонуємо тільки найкращі речі\n\n"
        "🚚 <b>Швидка доставка</b>\n"
        "Доставка по всій Україні\n\n"
        "💳 <b>Зручна оплата</b>\n"
        "Безпечні методи оплати\n\n"
        "📞 <b>Підтримка</b>\n"
        "Завжди на зв'язку для вас"
    )
    
    await message.answer(info_text, parse_mode="HTML")

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
    await state.set_state(AddProduct.sizes)
    await callback.message.edit_text(
        "📏 <b>Останній крок!</b>\n\n"
        "Введіть доступні розміри через кому\n"
        "<i>Приклад: S, M, L, XL</i>",
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
            "одяг", 
            message.text
        )
        
        success_text = (
            "✅ <b>Товар успішно додано!</b>\n\n"
            f"🆔 ID: #{product_id}\n"
            f"📦 Назва: {data['name']}\n"
            f"💰 Ціна: {data['price']} грн\n"
            f"📁 Категорія: {data['category']}\n"
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
    
    products = get_all_products()
    
    if not products:
        await callback.message.edit_text(
            "📦 <b>Список товарів порожній</b>",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML"
        )
        return await callback.answer()
    
    products_text = "📦 <b>Список товарів:</b>\n\n"
    for p in products[:10]:  # Показуємо перші 10
        products_text += (
            f"🆔 #{p[0]} | {p[1]}\n"
            f"💰 {p[3]} грн | 📁 {p[5]}\n\n"
        )
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    
    await callback.message.edit_text(
        products_text,
        reply_markup=back_keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

# =======================
# LIST ORDERS
# =======================
@dp.callback_query(F.data == "list_orders")
async def list_orders_handler(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("❌ Немає доступу", show_alert=True)
    
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
        orders_text += (
            f"🆔 #{o[0]} | @{o[2] or 'Unknown'}\n"
            f"💰 {o[4]} грн\n"
            f"📅 {o[5]}\n\n"
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

# =======================
# WEBHOOK APP
# =======================
async def on_startup(app: web.Application):
    init_db()
    await bot.set_webhook(
        url=f"{WEBHOOK_URL}/webhook/bot",
        drop_pending_updates=True
    )
    logging.info("✅ Webhook встановлено")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    logging.info("❌ Webhook видалено")

app = web.Application()
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook/bot")
setup_application(app, dp, bot=bot)

if __name__ == "__main__":
    web.run_app(app, port=PORT)
