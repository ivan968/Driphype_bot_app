"""
Об'єднаний сервіс - API + Bot в одному процесі
"""
import os
import threading
import asyncio
from api_server import app
from bot import main as bot_main

def run_bot():
    """Запустити бота в окремому потоці"""
    asyncio.run(bot_main())

def run_api():
    """Запустити Flask API"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    print("🚀 Starting combined service (API + Bot)")
    
    # Запускаємо бота в окремому потоці
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("✅ Bot thread started")
    
    # Запускаємо API в головному потоці
    print("✅ Starting API server...")
    run_api()
