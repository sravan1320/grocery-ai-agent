"""
Database initialization and management utilities.
Handles SQLite schema creation and CSV imports.
"""

import sqlite3
import csv
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "grocery_agent.db"


def get_db_connection():
    """Get SQLite database connection."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        logger.info(f"Connected to database: {DB_PATH}")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


def init_database():
    """Initialize database schema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                vendor TEXT NOT NULL,
                product_name TEXT NOT NULL,
                brand TEXT,
                weight FLOAT,
                unit TEXT,
                price FLOAT,
                category TEXT,
                stock_status TEXT DEFAULT 'in_stock',
                expiry_days INTEGER DEFAULT 365,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Agent memory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_memory (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                memory_type TEXT,
                content TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Cart history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cart_history (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                product_name TEXT,
                brand TEXT,
                vendor TEXT,
                price FLOAT,
                quantity INTEGER,
                decision_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY,
                preference_key TEXT UNIQUE,
                preference_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        logger.info("Database schema created successfully")
        
        # Import CSV data
        import_csv_data()
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        conn.close()


def import_csv_data():
    """Import products from CSV file."""
    csv_path = Path(__file__).parent.parent.parent / "data" / "products.csv"
    
    if not csv_path.exists():
        logger.warning(f"CSV file not found: {csv_path}")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Clear existing data
        cursor.execute("DELETE FROM products")
        
        # Import from CSV
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute("""
                    INSERT INTO products 
                    (vendor, product_name, brand, weight, unit, price, category, stock_status, expiry_days)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['vendor'],
                    row['product_name'],
                    row['brand'],
                    float(row['weight']),
                    row['unit'],
                    float(row['price']),
                    row['category'],
                    row.get('stock_status', 'in_stock'),
                    int(row.get('expiry_days', 365))
                ))
        
        conn.commit()
        logger.info(f"Imported {cursor.rowcount} products from CSV")
    
    except Exception as e:
        logger.error(f"Failed to import CSV data: {e}")
        raise
    finally:
        conn.close()
