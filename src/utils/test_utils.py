"""
Utility functions for testing and debugging.
"""

import requests
import logging
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import get_db_connection
from models.grocery_list import ParsedGroceryList, ParsedGroceryItem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def test_database():
    """Test database connectivity."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM products")
        count = cursor.fetchone()[0]
        
        conn.close()
        
        logger.info(f"✅ Database OK: {count} products found")
        return True
    except Exception as e:
        logger.error(f"❌ Database failed: {e}")
        return False


def test_api_connectivity():
    """Test FastAPI connectivity."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ FastAPI OK")
            return True
        else:
            logger.error(f"❌ FastAPI returned {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ FastAPI failed: {e}")
        return False


def test_llm_connectivity():
    """Test Ollama/LLM connectivity."""
    try:
        import ollama
        # Test simple model call
        response = ollama.chat(
            model="qwen2.5:7b",
            messages=[{"role": "user", "content": "Say OK"}],
            stream=False
        )
        logger.info("✅ Ollama OK")
        return True
    except Exception as e:
        logger.error(f"❌ Ollama failed: {e}")
        return False


def run_example_agent():
    """Run a quick example with the agent."""
    from ..agents import execute_agent
    
    try:
        # Simple grocery list
        items = [
            ParsedGroceryItem(item_name="basmati_rice", quantity=5, unit="kg"),
            ParsedGroceryItem(item_name="fabric_conditioner", quantity=2, unit="l"),
        ]
        
        grocery_list = ParsedGroceryList(
            items=items,
            original_input="5kg basmati rice, 2L fabric conditioner"
        )
        
        logger.info("Running example agent...")
        result = execute_agent(grocery_list)
        
        logger.info(f"✅ Agent ran successfully. Cart: {len(result.current_cart.items)} items")
        return True
    except Exception as e:
        logger.error(f"❌ Agent failed: {e}")
        return False


def health_check():
    """Run all health checks."""
    print("\n" + "="*50)
    print("HEALTH CHECK")
    print("="*50)
    
    checks = {
        "Database": test_database(),
        "FastAPI": test_api_connectivity(),
        "Ollama/LLM": test_llm_connectivity(),
    }
    
    print("\nResults:")
    for name, result in checks.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
    
    print("="*50 + "\n")
    
    return all(checks.values())


if __name__ == "__main__":
    health_check()
