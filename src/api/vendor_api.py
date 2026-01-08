"""
FastAPI service that exposes vendor APIs querying SQLite database.
Each vendor endpoint returns product variants from the database.
Simulates real vendor behavior with realistic pricing and availability.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pathlib import Path
import logging
import json
from datetime import datetime
from typing import List, Optional
import asyncio
from src.models.product import ProductVariant
from src.models.api import VendorAPIResponse, APIError
    
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Grocery Vendor APIs")

# Enable CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "grocery_agent.db"


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def product_row_to_variant(row: sqlite3.Row) -> ProductVariant:
    """Convert database row to ProductVariant model."""
    return ProductVariant(
        vendor=row["vendor"],
        product_name=row["product_name"],
        brand=row["brand"],
        weight=float(row["weight"]),
        unit=row["unit"],
        price=float(row["price"]),
        category=row["category"],
        stock_status=row["stock_status"],
        expiry_days=row["expiry_days"]
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/zepto/search")
def zepto_search(product_name: str) -> VendorAPIResponse:
    """
    Search for products in Zepto vendor database.
    Returns all variants (brands, sizes, prices) for the product.
    """
    logger.info(f"Zepto search: {product_name}")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Normalize product name for search
        search_term = product_name.lower().replace(" ", "_")
        
        cursor.execute("""
            SELECT * FROM products 
            WHERE vendor = 'zepto' AND product_name = ?
            ORDER BY price ASC
        """, (search_term,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            logger.warning(f"No products found for {product_name} in Zepto")
            return VendorAPIResponse(
                product_name=product_name,
                variants=[],
                api_vendor="zepto",
                status="no_results"
            )
        
        variants = [product_row_to_variant(row) for row in rows]
        
        return VendorAPIResponse(
            product_name=product_name,
            variants=variants,
            api_vendor="zepto",
            status="success"
        )
    
    except Exception as e:
        logger.error(f"Zepto API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/blinkit/search")
def blinkit_search(product_name: str) -> VendorAPIResponse:
    """Search for products in Blinkit vendor database."""
    logger.info(f"Blinkit search: {product_name}")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        search_term = product_name.lower().replace(" ", "_")
        
        cursor.execute("""
            SELECT * FROM products 
            WHERE vendor = 'blinkit' AND product_name = ?
            ORDER BY price ASC
        """, (search_term,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            logger.warning(f"No products found for {product_name} in Blinkit")
            return VendorAPIResponse(
                product_name=product_name,
                variants=[],
                api_vendor="blinkit",
                status="no_results"
            )
        
        variants = [product_row_to_variant(row) for row in rows]
        
        return VendorAPIResponse(
            product_name=product_name,
            variants=variants,
            api_vendor="blinkit",
            status="success"
        )
    
    except Exception as e:
        logger.error(f"Blinkit API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/swiggy_instamart/search")
def swiggy_search(product_name: str) -> VendorAPIResponse:
    """Search for products in Swiggy Instamart vendor database."""
    logger.info(f"Swiggy search: {product_name}")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        search_term = product_name.lower().replace(" ", "_")
        
        cursor.execute("""
            SELECT * FROM products 
            WHERE vendor = 'swiggy_instamart' AND product_name = ?
            ORDER BY price ASC
        """, (search_term,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            logger.warning(f"No products found for {product_name} in Swiggy Instamart")
            return VendorAPIResponse(
                product_name=product_name,
                variants=[],
                api_vendor="swiggy_instamart",
                status="no_results"
            )
        
        variants = [product_row_to_variant(row) for row in rows]
        
        return VendorAPIResponse(
            product_name=product_name,
            variants=variants,
            api_vendor="swiggy_instamart",
            status="success"
        )
    
    except Exception as e:
        logger.error(f"Swiggy API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bigbasket/search")
def bigbasket_search(product_name: str) -> VendorAPIResponse:
    """Search for products in BigBasket vendor database."""
    logger.info(f"BigBasket search: {product_name}")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        search_term = product_name.lower().replace(" ", "_")
        
        cursor.execute("""
            SELECT * FROM products 
            WHERE vendor = 'bigbasket' AND product_name = ?
            ORDER BY price ASC
        """, (search_term,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            logger.warning(f"No products found for {product_name} in BigBasket")
            return VendorAPIResponse(
                product_name=product_name,
                variants=[],
                api_vendor="bigbasket",
                status="no_results"
            )
        
        variants = [product_row_to_variant(row) for row in rows]
        
        return VendorAPIResponse(
            product_name=product_name,
            variants=variants,
            api_vendor="bigbasket",
            status="success"
        )
    
    except Exception as e:
        logger.error(f"BigBasket API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search-all")
def search_all_vendors(product_name: str) -> dict:
    """Search across all vendors simultaneously."""
    logger.info(f"Multi-vendor search: {product_name}")
    
    results = {
        "zepto": zepto_search(product_name),
        "blinkit": blinkit_search(product_name),
        "swiggy_instamart": swiggy_search(product_name),
        "bigbasket": bigbasket_search(product_name)
    }
    
    return results


@app.get("/api/stats")
def get_stats():
    """Get database statistics."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM products")
        total_products = cursor.fetchone()["count"]
        
        cursor.execute("SELECT DISTINCT vendor FROM products")
        vendors = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT COUNT(DISTINCT product_name) as count FROM products")
        unique_products = cursor.fetchone()["count"]
        
        conn.close()
        
        return {
            "total_variants": total_products,
            "vendors": vendors,
            "unique_products": unique_products,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
