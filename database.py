"""
Database helper - підтримує як SQLite (локально) так і PostgreSQL (production)
"""
import os
from urllib.parse import urlparse

# Перевіряємо чи є DATABASE_URL (Render автоматично додає для PostgreSQL)
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Production: PostgreSQL
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    # Render використовує postgres://, а psycopg2 потребує postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    def get_connection():
        """Отримати з'єднання з PostgreSQL"""
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    
    def init_db():
        """Ініціалізація PostgreSQL бази"""
        conn = get_connection()
        c = conn.cursor()
        
        # Products table
        c.execute('''CREATE TABLE IF NOT EXISTS products
                     (id SERIAL PRIMARY KEY,
                      name TEXT NOT NULL,
                      description TEXT,
                      price REAL NOT NULL,
                      image_url TEXT,
                      category TEXT,
                      product_type TEXT,
                      sizes TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Orders table
        c.execute('''CREATE TABLE IF NOT EXISTS orders
                     (id SERIAL PRIMARY KEY,
                      user_id BIGINT NOT NULL,
                      username TEXT,
                      products TEXT NOT NULL,
                      total_price REAL NOT NULL,
                      status TEXT DEFAULT 'pending',
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id BIGINT PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      last_name TEXT,
                      is_admin INTEGER DEFAULT 0,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
        print("✅ PostgreSQL database initialized")
    
    def execute_query(query, params=None, fetch=False, fetchone=False):
        """Виконати SQL запит"""
        conn = get_connection()
        c = conn.cursor()
        
        if params:
            c.execute(query, params)
        else:
            c.execute(query)
        
        result = None
        if fetch:
            result = c.fetchall()
        elif fetchone:
            result = c.fetchone()
        
        if not fetch and not fetchone:
            conn.commit()
            if 'INSERT' in query.upper() and 'RETURNING' not in query.upper():
                c.execute('SELECT lastval()')
                result = c.fetchone()[0] if c.rowcount > 0 else None
        
        conn.close()
        return result

else:
    # Development: SQLite
    import sqlite3
    
    DB_FILE = 'shop.db'
    
    def get_connection():
        """Отримати з'єднання з SQLite"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db():
        """Ініціалізація SQLite бази"""
        conn = get_connection()
        c = conn.cursor()
        
        # Products table
        c.execute('''CREATE TABLE IF NOT EXISTS products
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      description TEXT,
                      price REAL NOT NULL,
                      image_url TEXT,
                      category TEXT,
                      product_type TEXT,
                      sizes TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Orders table
        c.execute('''CREATE TABLE IF NOT EXISTS orders
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER NOT NULL,
                      username TEXT,
                      products TEXT NOT NULL,
                      total_price REAL NOT NULL,
                      status TEXT DEFAULT 'pending',
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      last_name TEXT,
                      is_admin INTEGER DEFAULT 0,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
        print("✅ SQLite database initialized")
    
    def execute_query(query, params=None, fetch=False, fetchone=False):
        """Виконати SQL запит"""
        conn = get_connection()
        c = conn.cursor()
        
        if params:
            c.execute(query, params)
        else:
            c.execute(query)
        
        result = None
        if fetch:
            result = [dict(row) for row in c.fetchall()]
        elif fetchone:
            row = c.fetchone()
            result = dict(row) if row else None
        
        if not fetch and not fetchone:
            conn.commit()
            result = c.lastrowid if c.lastrowid else None
        
        conn.close()
        return result


# Загальні функції для роботи з БД
def get_all_products():
    """Отримати всі товари"""
    return execute_query('SELECT * FROM products ORDER BY created_at DESC', fetch=True)


def get_product(product_id):
    """Отримати один товар"""
    return execute_query('SELECT * FROM products WHERE id = %s' if DATABASE_URL else 'SELECT * FROM products WHERE id = ?', 
                        (product_id,), fetchone=True)


def add_product(name, description, price, image_url, category, product_type, sizes):
    """Додати товар"""
    query = '''INSERT INTO products (name, description, price, image_url, category, product_type, sizes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)''' if DATABASE_URL else \
            '''INSERT INTO products (name, description, price, image_url, category, product_type, sizes)
               VALUES (?, ?, ?, ?, ?, ?, ?)'''
    return execute_query(query, (name, description, price, image_url, category, product_type, sizes))


def delete_product(product_id):
    """Видалити товар"""
    query = 'DELETE FROM products WHERE id = %s' if DATABASE_URL else 'DELETE FROM products WHERE id = ?'
    execute_query(query, (product_id,))


def add_order(user_id, username, products, total_price):
    """Додати замовлення"""
    query = '''INSERT INTO orders (user_id, username, products, total_price)
               VALUES (%s, %s, %s, %s)''' if DATABASE_URL else \
            '''INSERT INTO orders (user_id, username, products, total_price)
               VALUES (?, ?, ?, ?)'''
    return execute_query(query, (user_id, username, products, total_price))


def get_recent_orders(limit=10):
    """Отримати останні замовлення"""
    query = 'SELECT * FROM orders ORDER BY created_at DESC LIMIT %s' if DATABASE_URL else \
            'SELECT * FROM orders ORDER BY created_at DESC LIMIT ?'
    return execute_query(query, (limit,), fetch=True)


def save_user(user_id, username, first_name, last_name, is_admin=0):
    """Зберегти користувача"""
    if DATABASE_URL:
        query = '''INSERT INTO users (user_id, username, first_name, last_name, is_admin)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET
                   username = EXCLUDED.username,
                   first_name = EXCLUDED.first_name,
                   last_name = EXCLUDED.last_name,
                   is_admin = EXCLUDED.is_admin'''
    else:
        query = '''INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, is_admin)
                   VALUES (?, ?, ?, ?, ?)'''
    
    execute_query(query, (user_id, username, first_name, last_name, is_admin))