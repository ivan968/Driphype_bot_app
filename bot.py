import os
import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime
from dotenv import load_dotenv

# Імпортуємо наш database helper
from database import (
    init_db, get_all_products, get_product, add_product, 
    delete_product, add_order, get_recent_orders, save_user
)

load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)

# Environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBAPP_URL = os.getenv('WEBAPP_URL')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# FSM States for adding products
class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    image_url = State()
    category = State()
    product_type = State()
    sizes = State()

# Check if user is admin
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# Start command
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Save user to database
    save_user(
        user_id, 
        message.from_user.username, 
        message.from_user.first_name,
        message.from_user.last_name, 
        1 if is_admin(user_id) else 0
    )
    
    # Create keyboard with web app
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ Відкрити магазин", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="ℹ️ Про магазин", callback_data="about")]
    ])
    
    if is_admin(user_id):
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="⚙️ Адмін панель", callback_data="admin")]
        )
    
    await message.answer(
        f"👋 Привіт, {message.from_user.first_name}!\n\n"
        "🛍️ Ласкаво просимо до нашого магазину одягу!\n\n"
        "Натисніть кнопку нижче, щоб переглянути наш асортимент:",
        reply_markup=keyboard
    )

# Admin panel
@dp.callback_query(F.data == "admin")
async def admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас немає доступу до адмін панелі", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Додати товар", callback_data="add_product")],
        [InlineKeyboardButton(text="📦 Список товарів", callback_data="list_products")],
        [InlineKeyboardButton(text="🗑️ Видалити товар", callback_data="delete_product_menu")],
        [InlineKeyboardButton(text="📊 Замовлення", callback_data="list_orders")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")]
    ])
    
    await callback.message.edit_text(
        "⚙️ <b>Адмін панель</b>\n\n"
        "Оберіть дію:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Add product flow
@dp.callback_query(F.data == "add_product")
async def start_add_product(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас немає доступу", show_alert=True)
        return
    
    await state.set_state(AddProduct.name)
    await callback.message.edit_text("📝 Введіть назву товару:")

@dp.message(AddProduct.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.description)
    await message.answer("📝 Введіть опис товару:")

@dp.message(AddProduct.description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("💰 Введіть ціну товару (число):")

@dp.message(AddProduct.price)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)
        await state.set_state(AddProduct.image_url)
        await message.answer("🖼️ Введіть URL зображення товару:")
    except ValueError:
        await message.answer("❌ Невірний формат ціни. Введіть число:")

@dp.message(AddProduct.image_url)
async def process_image(message: types.Message, state: FSMContext):
    await state.update_data(image_url=message.text)
    await state.set_state(AddProduct.category)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Чоловіче", callback_data="cat_чоловіче")],
        [InlineKeyboardButton(text="👩 Жіноче", callback_data="cat_жіноче")],
        [InlineKeyboardButton(text="👶 Дитяче", callback_data="cat_дитяче")],
        [InlineKeyboardButton(text="🎒 Аксесуари", callback_data="cat_аксесуари")]
    ])
    
    await message.answer("📁 Оберіть категорію:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("cat_", "")
    await state.update_data(category=category)
    await state.set_state(AddProduct.product_type)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👕 Футболка", callback_data="type_футболка")],
        [InlineKeyboardButton(text="👖 Штани", callback_data="type_штани")],
        [InlineKeyboardButton(text="👗 Сукня", callback_data="type_сукня")],
        [InlineKeyboardButton(text="🧥 Куртка", callback_data="type_куртка")],
        [InlineKeyboardButton(text="👟 Взуття", callback_data="type_взуття")],
        [InlineKeyboardButton(text="🎽 Спортивний одяг", callback_data="type_спортивний")],
        [InlineKeyboardButton(text="👔 Костюм", callback_data="type_костюм")],
        [InlineKeyboardButton(text="🎒 Аксесуар", callback_data="type_аксесуар")]
    ])
    
    await callback.message.edit_text("🏷️ Оберіть тип товару:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("type_"))
async def process_product_type(callback: types.CallbackQuery, state: FSMContext):
    product_type = callback.data.replace("type_", "")
    await state.update_data(product_type=product_type)
    await state.set_state(AddProduct.sizes)
    
    if product_type == "взуття":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Використати стандартні розміри взуття", callback_data="sizes_shoes")]
        ])
        await callback.message.edit_text(
            "📏 Введіть розміри через кому або натисніть кнопку для стандартних розмірів взуття (30-46):",
            reply_markup=keyboard
        )
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Використати стандартні розміри одягу", callback_data="sizes_standard")]
        ])
        await callback.message.edit_text(
            "📏 Введіть розміри через кому або натисніть кнопку для стандартних розмірів (XS,S,M,L,XL,XXL):",
            reply_markup=keyboard
        )

@dp.callback_query(F.data == "sizes_shoes")
async def set_shoe_sizes(callback: types.CallbackQuery, state: FSMContext):
    sizes = ",".join([str(i) for i in range(30, 47)])
    await finalize_product(callback.message, state, sizes)

@dp.callback_query(F.data == "sizes_standard")
async def set_standard_sizes(callback: types.CallbackQuery, state: FSMContext):
    sizes = "XS,S,M,L,XL,XXL"
    await finalize_product(callback.message, state, sizes)

@dp.message(AddProduct.sizes)
async def process_sizes(message: types.Message, state: FSMContext):
    await finalize_product(message, state, message.text)

async def finalize_product(message, state: FSMContext, sizes: str):
    await state.update_data(sizes=sizes)
    data = await state.get_data()
    
    # Save to database
    product_id = add_product(
        data['name'], 
        data['description'], 
        data['price'], 
        data['image_url'], 
        data['category'], 
        data['product_type'], 
        sizes
    )
    
    await message.answer(
        f"✅ Товар #{product_id} успішно додано!\n\n"
        f"📦 {data['name']}\n"
        f"🏷️ {data['product_type']}\n"
        f"💰 {data['price']} грн\n"
        f"📁 {data['category']}\n"
        f"📏 Розміри: {sizes}"
    )
    
    await state.clear()

# Delete product menu
@dp.callback_query(F.data == "delete_product_menu")
async def delete_product_menu(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас немає доступу", show_alert=True)
        return
    
    products = get_all_products()[:20]  # Перші 20
    
    if not products:
        await callback.message.edit_text("📦 Товарів немає")
        return
    
    keyboard_buttons = []
    for p in products:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"🗑️ {p['name']} ({p['price']} грн)", 
                callback_data=f"del_prod_{p['id']}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(
        "🗑️ <b>Видалити товар</b>\n\nОберіть товар для видалення:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("del_prod_"))
async def confirm_delete_product(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас немає доступу", show_alert=True)
        return
    
    product_id = int(callback.data.replace("del_prod_", ""))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Так, видалити", callback_data=f"confirm_del_{product_id}"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data="delete_product_menu")
        ]
    ])
    
    await callback.message.edit_text(
        f"⚠️ Ви впевнені, що хочете видалити товар #{product_id}?",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("confirm_del_"))
async def execute_delete_product(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас немає доступу", show_alert=True)
        return
    
    product_id = int(callback.data.replace("confirm_del_", ""))
    delete_product(product_id)
    
    await callback.answer("✅ Товар видалено!", show_alert=True)
    await delete_product_menu(callback)

# List products
@dp.callback_query(F.data == "list_products")
async def list_products(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас немає доступу", show_alert=True)
        return
    
    products = get_all_products()[:15]  # Перші 15
    
    if not products:
        await callback.message.edit_text("📦 Товарів ще немає")
        return
    
    text = "📦 <b>Список товарів:</b>\n\n"
    for p in products:
        text += f"🆔 {p['id']} | {p['name']}\n💰 {p['price']} грн | {p['product_type']} | {p['category']}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# List orders
@dp.callback_query(F.data == "list_orders")
async def list_orders(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас немає доступу", show_alert=True)
        return
    
    orders = get_recent_orders(10)
    
    if not orders:
        text = "📊 Замовлень ще немає"
    else:
        text = "📊 <b>Останні замовлення:</b>\n\n"
        for o in orders:
            created_at = str(o['created_at'])[:16] if o.get('created_at') else 'N/A'
            text += f"🆔 #{o['id']} | @{o['username'] or 'без username'}\n💰 {o['total_price']} грн | {created_at}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# Web App Data Handler
@dp.message(F.content_type == types.ContentType.WEB_APP_DATA)
async def web_app_data(message: types.Message):
    data = json.loads(message.web_app_data.data)
    
    if data.get('type') == 'order':
        # Save order to database
        order_id = add_order(
            message.from_user.id, 
            message.from_user.username,
            json.dumps(data['products']), 
            data['total']
        )
        
        # Notify admin
        if ADMIN_ID:
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"🔔 <b>Нове замовлення #{order_id}!</b>\n\n"
                    f"👤 @{message.from_user.username or 'без username'}\n"
                    f"💰 Сума: {data['total']} грн\n"
                    f"📦 Товарів: {len(data['products'])}",
                    parse_mode="HTML"
                )
            except:
                pass
        
        await message.answer(
            f"✅ Замовлення #{order_id} прийнято!\n\n"
            f"💰 Сума: {data['total']} грн\n"
            f"📦 Товарів: {len(data['products'])}\n\n"
            "Ми зв'яжемося з вами найближчим часом!"
        )

# About callback
@dp.callback_query(F.data == "about")
async def about(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")]
    ])
    
    await callback.message.edit_text(
        "ℹ️ <b>Про наш магазин</b>\n\n"
        "🛍️ Ми пропонуємо якісний одяг за доступними цінами!\n\n"
        "📱 Оформляйте замовлення прямо в Telegram\n"
        "🚚 Швидка доставка по всій Україні\n"
        "💳 Зручна оплата\n\n"
        "📞 Підтримка: @your_support",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery):
    await cmd_start(callback.message)

# Main function
async def main():
    print("\n🔄 Ініціалізація бази даних...")
    init_db()
    print("✅ Bot started successfully!")
    print("📱 Бот готовий приймати повідомлення...\n")
    await dp.start_polling(bot)
