"""
API сервер для динамічного завантаження товарів
"""
from flask import Flask, jsonify
from flask_cors import CORS
from database import get_all_products, get_product, init_db

app = Flask(__name__)
CORS(app)  # Дозволяємо запити з будь-яких доменів

# Ініціалізуємо базу при старті
try:
    init_db()
    print("✅ Database initialized on startup")
except Exception as e:
    print(f"⚠️ Database init warning: {e}")

@app.route('/', methods=['GET'])
def home():
    """Головна сторінка API"""
    return jsonify({
        'status': 'online',
        'message': 'Driphype Shop API is running',
        'endpoints': {
            '/api/products': 'GET - Отримати всі товари',
            '/api/products/<id>': 'GET - Отримати товар за ID',
            '/api/init': 'POST - Ініціалізувати базу даних'
        }
    })

@app.route('/api/init', methods=['GET', 'POST'])
def initialize_db():
    """Ініціалізувати базу даних"""
    try:
        init_db()
        return jsonify({'status': 'success', 'message': 'Database initialized'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/products', methods=['GET'])
def get_products():
    """Отримати всі товари з бази даних"""
    try:
        products = get_all_products()
        return jsonify(products)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product_by_id(product_id):
    """Отримати один товар"""
    try:
        product = get_product(product_id)
        
        if product:
            return jsonify(product)
        else:
            return jsonify({'error': 'Product not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint для Render"""
    return jsonify({'status': 'healthy'}), 200

# Flask app ready to be imported by main.py or gunicorn
