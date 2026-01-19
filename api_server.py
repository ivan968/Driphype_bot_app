"""
API сервер для динамічного завантаження товарів
"""
from flask import Flask, jsonify
from flask_cors import CORS
from database import get_all_products, get_product

app = Flask(__name__)
CORS(app)  # Дозволяємо запити з будь-яких доменів

@app.route('/', methods=['GET'])
def home():
    """Головна сторінка API"""
    return jsonify({
        'status': 'online',
        'message': 'Driphype Shop API is running',
        'endpoints': {
            '/api/products': 'GET - Отримати всі товари',
            '/api/products/<id>': 'GET - Отримати товар за ID'
        }
    })

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

if __name__ == '__main__':
    # Запускаємо сервер
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)