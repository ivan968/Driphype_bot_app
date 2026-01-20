"""
Об'єднаний сервіс - API + Bot через Webhook
"""
import os
import asyncio
import json
from datetime import datetime
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from bot import dp, bot, init_db

# Custom JSON encoder для datetime
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Webhook settings
WEBHOOK_PATH = "/webhook/bot"
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://driphype-api.onrender.com/webhook/bot')

# Routes для API
routes = web.RouteTableDef()

@routes.get('/')
async def home(request):
    """Головна сторінка API"""
    return web.json_response({
        'status': 'online',
        'message': 'Driphype Shop API is running',
        'mode': 'webhook',
        'endpoints': {
            '/api/products': 'GET - Отримати всі товари',
            '/api/products/{id}': 'GET - Отримати товар за ID',
            '/webhook/bot': 'POST - Telegram webhook'
        }
    })

@routes.get('/api/products')
async def get_products(request):
    """Отримати всі товари"""
    try:
        from database import get_all_products
        # Викликаємо синхронну функцію в executor
        loop = asyncio.get_event_loop()
        products = await loop.run_in_executor(None, get_all_products)
        
        # Конвертуємо datetime в string
        return web.Response(
            text=json.dumps(products, cls=DateTimeEncoder),
            content_type='application/json'
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({'error': str(e)}, status=500)

@routes.get('/api/products/{product_id}')
async def get_product(request):
    """Отримати один товар"""
    try:
        from database import get_product as db_get_product
        product_id = int(request.match_info['product_id'])
        
        # Викликаємо синхронну функцію в executor
        loop = asyncio.get_event_loop()
        product = await loop.run_in_executor(None, db_get_product, product_id)
        
        if product:
            # Конвертуємо datetime в string
            return web.Response(
                text=json.dumps(product, cls=DateTimeEncoder),
                content_type='application/json'
            )
        else:
            return web.json_response({'error': 'Product not found'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({'error': str(e)}, status=500)

@routes.get('/health')
async def health(request):
    """Health check"""
    return web.json_response({'status': 'healthy'})

# CORS middleware
@web.middleware
async def cors_middleware(request, handler):
    """Додати CORS headers"""
    if request.method == 'OPTIONS':
        response = web.Response()
    else:
        response = await handler(request)
    
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

async def on_startup(app):
    """Налаштування webhook при старті"""
    print("🚀 Setting up webhook...")
    
    # Ініціалізуємо БД в executor (синхронна функція)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, init_db)
    
    # Видаляємо старий webhook
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Old webhook deleted")
    
    # Встановлюємо новий webhook
    webhook_info = await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )
    print(f"✅ Webhook set to: {WEBHOOK_URL}")
    print(f"   Webhook info: {webhook_info}")

async def on_shutdown(app):
    """Видалення webhook при зупинці"""
    print("🛑 Removing webhook...")
    await bot.delete_webhook()
    await bot.session.close()

def create_app():
    """Створити aiohttp application"""
    app = web.Application(middlewares=[cors_middleware])
    app.add_routes(routes)
    
    # Налаштування webhook handler
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    return app

if __name__ == '__main__':
    print("🚀 Starting combined service (API + Bot via Webhook)")
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    web.run_app(app, host='0.0.0.0', port=port)
