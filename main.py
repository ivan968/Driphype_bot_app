"""
Об'єднаний сервіс - API + Bot в одному процесі
Використовує aiohttp для API і aiogram для бота в одному event loop
"""
import os
import asyncio
from aiohttp import web
from bot import dp, bot, init_db

# Routes для API
routes = web.RouteTableDef()

@routes.get('/')
async def home(request):
    """Головна сторінка API"""
    return web.json_response({
        'status': 'online',
        'message': 'Driphype Shop API is running',
        'endpoints': {
            '/api/products': 'GET - Отримати всі товари',
            '/api/products/{id}': 'GET - Отримати товар за ID'
        }
    })

@routes.get('/api/products')
async def get_products(request):
    """Отримати всі товари"""
    try:
        from database import get_all_products
        products = get_all_products()
        return web.json_response(products)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

@routes.get('/api/products/{product_id}')
async def get_product(request):
    """Отримати один товар"""
    try:
        from database import get_product as db_get_product
        product_id = int(request.match_info['product_id'])
        product = db_get_product(product_id)
        
        if product:
            return web.json_response(product)
        else:
            return web.json_response({'error': 'Product not found'}, status=404)
    except Exception as e:
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
    """Запуск бота при старті сервера"""
    print("🚀 Starting Telegram bot...")
    init_db()
    asyncio.create_task(dp.start_polling(bot))
    print("✅ Bot started successfully!")

async def on_shutdown(app):
    """Зупинка бота"""
    print("🛑 Stopping bot...")
    await bot.session.close()

def create_app():
    """Створити aiohttp application"""
    app = web.Application(middlewares=[cors_middleware])
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

if __name__ == '__main__':
    print("🚀 Starting combined service (API + Bot)")
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    web.run_app(app, host='0.0.0.0', port=port)
