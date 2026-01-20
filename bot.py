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
    info_text = (
        "ℹ️ <b>Про DripHype</b>\n\n"
        "🎯 <b>Якість та стиль</b>\n"
        "Ми пропонуємо тільки найкращі речі\n\n"
        "🚚 <b>Швидка доставка</b>\n"
        "Доставка по всій Європі\n\n"
        "💳 <b>Зручна оплата</b>\n"
        "Безпечні методи оплати\n\n"
        "📞 <b>Підтримка тг</b>\n"
        "@soryuko - власник"
        "@whytodie - співпраця"
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

