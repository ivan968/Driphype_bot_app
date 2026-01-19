"""
Опціональний API сервер для динамічного завантаження товарів
Запускайте його тільки якщо хочете, щоб товари оновлювались автоматично
"""

from flask import Flask, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)  # Дозволяємо запити з будь-яких доменів

@app.route('/api/products', methods=['GET'])
def get_products():
    """Отримати всі товари з бази даних"""
    try:
        conn = sqlite3.connect('shop.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM products ORDER BY created_at DESC')
        products = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify(products)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Отримати один товар"""
    try:
        conn = sqlite3.connect('shop.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        product = c.fetchone()
        conn.close()
        
        if product:
            return jsonify(dict(product))
        else:
            return jsonify({'error': 'Product not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Запускаємо сервер на порті 5000
    app.run(host='0.0.0.0', port=5000, debug=True)