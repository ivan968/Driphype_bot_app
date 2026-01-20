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

# Глобальна змінна для контролю фонового таску
background_tasks = set()

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
            '/webhook/bot': 'POST - Telegram webhook',
            '/status': 'GET - Bot status dashboard',
            '/bot/update-webhook': 'GET - Force update webhook'
        }
    })

@routes.get('/api/products')
async def get_products(request):
    """Отримати всі товари"""
    try:
        from database import get_all_products
        loop = asyncio.get_event_loop()
        products = await loop.run_in_executor(None, get_all_products)
        
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
        
        loop = asyncio.get_event_loop()
        product = await loop.run_in_executor(None, db_get_product, product_id)
        
        if product:
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

# ============================================
# BOT STATUS DASHBOARD
# ============================================

@routes.get('/status')
async def bot_status(request):
    """HTML Dashboard для статусу бота"""
    try:
        webhook_info = await bot.get_webhook_info()
        bot_info = await bot.get_me()
        
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
                
                <a href="/bot/update-webhook" class="btn">🔄 Force Update Webhook</a>
                
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

@routes.get('/bot/update-webhook')
@routes.post('/bot/update-webhook')
async def update_webhook_manual(request):
    """Форсоване оновлення webhook"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
        
        result = await bot.set_webhook(
            url=WEBHOOK_URL,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        
        webhook_info = await bot.get_webhook_info()
        
        html = f"""
        <html>
        <head>
            <title>Webhook Updated</title>
            <meta http-equiv="refresh" content="3;url=/status">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    padding: 40px;
                    background: linear-gradient(135deg, #1a1a1a 0%, #2d1b4e 100%);
                    color: #fff;
                    margin: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                }}
                .container {{
                    background: rgba(0, 0, 0, 0.5);
                    padding: 40px;
                    border-radius: 15px;
                    box-shadow: 0 8px 32px rgba(168, 85, 247, 0.2);
                    text-align: center;
                }}
                h1 {{
                    color: #a855f7;
                }}
                a {{
                    color: #c084fc;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{'✅ Webhook успішно оновлено!' if result else '❌ Помилка оновлення'}</h1>
                <p><strong>Webhook URL:</strong> {webhook_info.url}</p>
                <p><strong>Pending Updates:</strong> {webhook_info.pending_update_count}</p>
                <p>Перенаправлення на dashboard через 3 секунди...</p>
                <p><a href="/status">Повернутися зараз</a></p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    except Exception as e:
        print(f"Error updating webhook: {e}")
        return web.Response(text=f"Error: {str(e)}", status=500)

# ============================================
# АВТОМАТИЧНИЙ МОНІТОРИНГ WEBHOOK
# ============================================

async def webhook_monitor():
    """Перевіряє та оновлює webhook кожні 3 хвилини"""
    print("🔄 Webhook monitor запущено!")
    
    await asyncio.sleep(30)  # Чекаємо 30 секунд після старту
    
    while True:
        try:
            webhook_info = await bot.get_webhook_info()
            expected_url = WEBHOOK_URL
            
            if not webhook_info.url or webhook_info.url != expected_url:
                print(f"⚠️ Webhook URL неправильний! Очікуємо: {expected_url}, Поточний: {webhook_info.url}")
                await bot.delete_webhook(drop_pending_updates=True)
                await asyncio.sleep(2)
                await bot.set_webhook(url=expected_url, drop_pending_updates=True)
                print(f"✅ Webhook автоматично оновлено на {expected_url}")
                
            elif webhook_info.pending_update_count > 30:
                print(f"⚠️ Багато pending updates: {webhook_info.pending_update_count}")
                await bot.delete_webhook(drop_pending_updates=True)
                await asyncio.sleep(2)
                await bot.set_webhook(url=expected_url, drop_pending_updates=True)
                print("✅ Webhook автоматично перезапущено через pending updates")
                
            else:
                print(f"✅ Webhook перевірено: OK (pending: {webhook_info.pending_update_count})")
            
        except asyncio.CancelledError:
            print("🛑 Webhook monitor зупинено")
            break
        except Exception as e:
            print(f"❌ Помилка в webhook monitor: {e}")
        
        await asyncio.sleep(180)  # Перевіряємо кожні 3 хвилини

# ============================================
# CORS MIDDLEWARE
# ============================================

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

# ============================================
# STARTUP / SHUTDOWN
# ============================================

async def on_startup(app):
    """Налаштування webhook при старті"""
    print("🚀 Setting up webhook...")
    
    # Ініціалізуємо БД
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, init_db)
    print("✅ Database initialized")
    
    # Видаляємо старий webhook
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Old webhook deleted")
    await asyncio.sleep(2)
    
    # Встановлюємо новий webhook
    webhook_info = await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )
    print(f"✅ Webhook set to: {WEBHOOK_URL}")
    print(f"   Result: {webhook_info}")
    
    # Перевіряємо встановлення
    await asyncio.sleep(1)
    check_info = await bot.get_webhook_info()
    print(f"📋 Webhook status: URL={check_info.url}, Pending={check_info.pending_update_count}")
    
    # Запускаємо фоновий моніторинг
    task = asyncio.create_task(webhook_monitor())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    print("🔄 Автоматичний моніторинг webhook запущено (перевірка кожні 3 хвилини)")

async def on_shutdown(app):
    """Видалення webhook при зупинці"""
    print("🛑 Removing webhook...")
    
    # Скасовуємо всі фонові таски
    for task in background_tasks:
        task.cancel()
    
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)
    
    await bot.delete_webhook()
    await bot.session.close()
    print("✅ Shutdown complete")

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
