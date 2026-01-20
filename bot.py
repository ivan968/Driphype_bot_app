import os
import json
import logging
from aiohttp import web
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
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
# START
# =======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    save_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
        1 if is_admin(message.from_user.id) else 0
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ Відкрити магазин", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="ℹ️ Про магазин", callback_data="about")]
    ])

    if is_admin(message.from_user.id):
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="⚙️ Адмін панель", callback_data="admin")]
        )

    await message.answer(
        f"👋 Привіт, {message.from_user.first_name}!\n\n"
        "🛍️ Ласкаво просимо до нашого магазину одягу!",
        reply_markup=keyboard
    )

# =======================
# ADMIN PANEL
# =======================
@dp.callback_query(F.data == "admin")
async def admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("❌ Немає доступу", show_alert=True)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Додати товар", callback_data="add_product")],
        [InlineKeyboardButton(text="📦 Список товарів", callback_data="list_products")],
        [InlineKeyboardButton(text="🗑️ Видалити товар", callback_data="delete_product_menu")],
        [InlineKeyboardButton(text="📊 Замовлення", callback_data="list_orders")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")]
    ])

    await callback.message.edit_text("⚙️ <b>Адмін панель</b>", reply_markup=keyboard, parse_mode="HTML")

# =======================
# ADD PRODUCT FLOW
# =======================
@dp.callback_query(F.data == "add_product")
async def start_add_product(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("❌ Немає доступу", show_alert=True)

    await state.set_state(AddProduct.name)
    await callback.message.edit_text("📝 Введіть назву товару:")

@dp.message(AddProduct.name)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.description)
    await message.answer("📝 Введіть опис:")

@dp.message(AddProduct.description)
async def add_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("💰 Введіть ціну:")

@dp.message(AddProduct.price)
async def add_price(message: types.Message, state: FSMContext):
    try:
        await state.update_data(price=float(message.text))
        await state.set_state(AddProduct.image_url)
        await message.answer("🖼️ URL зображення:")
    except ValueError:
        await message.answer("❌ Введіть число")

@dp.message(AddProduct.image_url)
async def add_image(message: types.Message, state: FSMContext):
    await state.update_data(image_url=message.text)
    await state.set_state(AddProduct.category)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Чоловіче", callback_data="cat_чоловіче")],
        [InlineKeyboardButton(text="👩 Жіноче", callback_data="cat_жіноче")]
    ])
    await message.answer("📁 Категорія:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_"))
async def add_category(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(category=callback.data.replace("cat_", ""))
    await state.set_state(AddProduct.sizes)
    await callback.message.edit_text("📏 Введіть розміри через кому:")

@dp.message(AddProduct.sizes)
async def finish_product(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id = add_product(
        data["name"], data["description"], data["price"],
        data["image_url"], data["category"], "одяг", message.text
    )
    await message.answer(f"✅ Товар #{product_id} додано")
    await state.clear()

# =======================
# WEB APP ORDERS
# =======================
@dp.message(F.content_type == types.ContentType.WEB_APP_DATA)
async def web_app_data(message: types.Message):
    data = json.loads(message.web_app_data.data)
    order_id = add_order(
        message.from_user.id,
        message.from_user.username,
        json.dumps(data["products"]),
        data["total"]
    )
    await message.answer(f"✅ Замовлення #{order_id} прийнято!")

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
