# Autonomous Grocery Shopping Super-Agent

A production-grade autonomous agent system for intelligent grocery shopping using LLM reasoning, multi-vendor API integration, and dynamic control flow.

## Architecture Overview

```
User Input
    ↓
[PLANNER] → Generate execution plan
    ↓
[EXECUTOR] → Parse list, fetch from APIs, compare prices, use LLM reasoning
    ↓
[OBSERVER] → Validate decisions
    ↓
[EXECUTOR] → Build cart
    ↓
[OBSERVER] → Ask for confirmation
    ↓
[REPLANNER] ↔ Handle user feedback (modify/remove/recompare)
    ↓
[REPLANNER] → Finalize checkout
```

## Tech Stack

- **Python 3.10+**
- **LangGraph** - Dynamic control flow (NOT static DAGs)
- **Ollama + Qwen 2.5 7B** - Local LLM for reasoning
- **FastAPI** - Vendor API simulation
- **Streamlit** - User interface
- **SQLite** - Persistent memory
- **Pydantic** - Strict data validation

## Features

✅ **True Autonomy** - Agent decides what to do next at runtime
✅ **Dynamic Planning** - Planner → Executor → Observer → Replanner loop
✅ **User Feedback Handling** - Modify, remove, or recompare items after cart creation
✅ **Persistent Memory** - SQLite for session recovery
✅ **Multi-Vendor Integration** - Zepto, Blinkit, Swiggy Instamart, BigBasket
✅ **LLM Reasoning** - Qwen 2.5 7B for intelligent comparisons
✅ **Retry Logic** - Exponential backoff for failed API calls
✅ **Data Validation** - Pydantic for all data structures
✅ **REST API** - FastAPI vendor service
✅ **Interactive UI** - Streamlit for user interaction

## Setup Instructions

### Quick Start

We provide automated setup scripts for all platforms using modern Python tooling (**uv**).

#### Windows
```bash
scripts\setup_windows.bat
```

#### Linux/Mac
```bash
chmod +x scripts/setup_linux.sh
scripts/setup_linux.sh
```

### Prerequisites

- Windows 10/11, Linux, or macOS
- Python 3.10+ installed
- Ollama installed (from https://ollama.ai)

### Manual Setup

If the scripts don't work, follow these steps:

```bash
# 1. Create Python virtual environment with uv
uv venv --python 3.12 .venv

# 2. Activate virtual environment
# Windows:
.venv\Scripts\activate.bat
# Linux/Mac:
source .venv/bin/activate

# 3. Install dependencies from pyproject.toml
uv pip install -e .

# 4. Initialize database
python -c "from src.core import init_database; init_database()"
```

### Ollama Setup

```bash
# Download and install Ollama from https://ollama.ai
# After installation, pull the Qwen 2.5 7B model:
ollama pull qwen2.5:7b

# Start Ollama service
ollama serve
```

### Start Services (in separate terminals)

**Terminal 1: Start FastAPI Vendor Service**
```powershell
cd "C:\Users\poorn\PycharmProjects\Grocery Agent"
.\venv\Scripts\Activate.ps1
python -m uvicorn src.vendor_api:app --host 127.0.0.1 --port 8000 --reload
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

**Terminal 2: Start Streamlit UI**
```powershell
cd "C:\Users\poorn\PycharmProjects\Grocery Agent"
.\venv\Scripts\Activate.ps1
streamlit run src/app.py
```

Expected output:
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

### 5. Verify Setup

- **Ollama**: `http://localhost:11434` (should respond)
- **FastAPI**: `http://localhost:8000/health` (should return `{"status": "healthy"}`)
- **Streamlit**: `http://localhost:8501` (UI should be accessible)

## Usage

### Via Streamlit UI

1. Open `http://localhost:8501` in browser
2. Enter your grocery list in natural language:
   ```
   basmati rice 5kg, fabric conditioner 2L, groundnut 500g
   ```
3. Click "Parse & Start"
4. Agent will automatically:
   - Parse your input
   - Search all vendors
   - Compare prices and quality
   - Use LLM reasoning
   - Build optimal cart
5. Review results and confirm

### Via Python Script

```python
from models import ParsedGroceryList, ParsedGroceryItem
from super_agent import execute_agent

# Create grocery list
items = [
    ParsedGroceryItem(item_name="basmati_rice", quantity=5, unit="kg"),
    ParsedGroceryItem(item_name="fabric_conditioner", quantity=2, unit="l"),
    ParsedGroceryItem(item_name="groundnut", quantity=0.5, unit="kg"),
]

grocery_list = ParsedGroceryList(
    items=items,
    original_input="5kg basmati rice, 2L fabric conditioner, 500g groundnut"
)

# Execute agent
final_state = execute_agent(grocery_list)

# Access results
print(f"Cart Total: ₹{final_state.current_cart.total_price}")
print(f"Items: {len(final_state.current_cart.items)}")

for item in final_state.current_cart.items:
    print(f"- {item.brand} {item.weight}{item.unit} from {item.vendor} - ₹{item.price}")
```

## Project Structure

```
Grocery Agent/
├── data/
│   ├── products.csv              # 150+ realistic products (4 vendors)
│   └── grocery_agent.db          # SQLite database (auto-created)
├── logs/                         # Agent execution logs
├── src/
│   ├── app.py                    # Streamlit UI
│   ├── db_init.py                # Database schema & initialization
│   ├── models.py                 # Pydantic data models
│   ├── vendor_api.py             # FastAPI vendor service
│   ├── llm_engine.py             # Ollama LLM integration
│   ├── super_agent.py            # LangGraph super-agent (core)
│   └── retry_utils.py            # Retry logic & validation
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Key Components

### 1. **LangGraph Super-Agent** (`super_agent.py`)

Implements autonomous control flow:
- **create_execution_plan()**: Generates execution plan
- **fetch_product_variants()**: Fetches from all vendor APIs
- **compare_and_rank_products()**: Normalizes and compares prices
- **apply_llm_reasoning()**: Uses Qwen 2.5 7B for decisions
- **validate_cart_decisions()**: Deterministic validation
- **assemble_shopping_cart()**: Builds final cart
- **request_user_confirmation()**: Gets user approval

Router function decides next action dynamically (NOT a fixed DAG).

### 2. **Replanner Agent** (`replanner.py`)

Handles user feedback after cart creation:
- **process_user_feedback()**: Analyzes user input and routes to appropriate handler
- **modify_cart_item()**: Change vendor, brand, or quantity for an item
- **remove_cart_item()**: Remove item from cart
- **recompare_product()**: Re-analyze a product with detailed comparison
- **confirm_checkout()**: Finalize cart and prepare for order

Enables dynamic re-planning without restarting the entire process.

### 3. **LLM Engine** (`llm_engine.py`)

- Parse natural language grocery lists
- Compare product variants with reasoning
- Make vendor/brand decisions
- Handle user queries
- All outputs validated against Pydantic schemas

### 4. **Vendor APIs** (`vendor_api.py`)

FastAPI service exposing:
- `/api/zepto/search?product_name=...`
- `/api/blinkit/search?product_name=...`
- `/api/swiggy_instamart/search?product_name=...`
- `/api/bigbasket/search?product_name=...`
- `/api/search-all?product_name=...`
- `/api/stats` - Database statistics

### 5. **Data Models** (`models.py`)

Strict Pydantic validation for:
- ProductVariant
- ParsedGroceryList
- Cart / CartItem
- ExecutionPlan
- AgentState
- LLMReasoningOutput
- And more...

### 6. **Retry & Validation** (`retry_utils.py`)

- Exponential backoff retry decorator
- API response validation
- LLM output validation
- Distinguishes transient vs permanent errors

## Agent Decision Flow

```
INPUT: "5kg basmati rice, 2L fabric conditioner"
  ↓
PARSE: {"items": [{"item_name": "basmati_rice", "quantity": 5, "unit": "kg"}, ...]}
  ↓
FETCH: Zepto, Blinkit, Swiggy, BigBasket (parallel)
  ↓
VARIANTS:
  basmati_rice:
    - Zepto: India Gate 1kg @ ₹320, Taj 500g @ ₹165, ...
    - Blinkit: India Gate 1kg @ ₹330, Taj 500g @ ₹170, ...
    - Swiggy: India Gate 1kg @ ₹315, Taj 500g @ ₹160, ...
    - BigBasket: India Gate 1kg @ ₹310, Taj 500g @ ₹158, ...
  ↓
LLM REASONING:
  "User needs 5kg. Best value is BigBasket: 5x 1kg India Gate @ ₹310 = ₹1550"
  Confidence: 0.95
  ↓
VALIDATE:
  ✓ Vendor is valid
  ✓ Price is positive
  ✓ Confidence is 0.95 (acceptable)
  ↓
BUILD CART:
  {
    "product_name": "basmati_rice",
    "brand": "India Gate",
    "vendor": "bigbasket",
    "price": 310,
    "quantity": 5,
    "decision_reason": "Best value at ₹310/kg"
  }
  ↓
ASK CONFIRMATION:
  "5x India Gate 1kg from BigBasket - ₹1550. Confirm?"
  
  ═══════════════════════════════════════════════════════
  
  ★ USER FEEDBACK LOOP (REPLANNER) ★
  
  OPTION 1: User asks "Why not Zepto?"
    ↓
  RECOMPARE:
    - Agent analyzes Zepto option in detail
    - Zepto: 5x 1kg @ ₹320 = ₹1600 (₹50 more expensive)
    - Response: "BigBasket saves ₹50. Would you still prefer Zepto?"
    - User can then confirm BigBasket or switch to Zepto
  
  OPTION 2: User says "Change to Blinkit for this"
    ↓
  MODIFY:
    - Agent updates cart item vendor to Blinkit
    - Recalculates: 5x 1kg @ ₹330 = ₹1650
    - Updates decision reason
    - Confirms: "✅ Updated to Blinkit - ₹330/kg"
    - Awaits further instructions or confirmation
  
  OPTION 3: User says "Remove basmati rice"
    ↓
  REMOVE:
    - Item deleted from cart
    - Cart total recalculated
    - Confirms: "✅ Removed basmati rice from cart"
    - Shows updated cart with fabric conditioner only
    - Awaits further modifications or checkout
  
  OPTION 4: User says "Confirm & Checkout"
    ↓
  CHECKOUT:
    - Finalizes shopping cart
    - Generates order summary
    - Shows all items with vendors and prices
    - Ready for purchase! ✅
```

## Customization

### Add New Products

Edit `data/products.csv`:
```csv
zepto,new_product,brand_name,500,g,250,category,180,in_stock
```

Then reinit database:
```powershell
python src/db_init.py
```

### Change LLM Model

In `src/llm_engine.py`:
```python
OLLAMA_MODEL = "mistral"  # Change from qwen2.5:7b to other Ollama models
```

### Adjust Retry Behavior

In `src/super_agent.py`:
```python
RETRY_CONFIG = RetryConfig(
    max_retries=5,  # More retries
    initial_backoff=2.0,  # Start with 2 seconds
    backoff_multiplier=3.0  # Triple wait time each attempt
)
```

## Troubleshooting

### "Ollama connection refused"
```powershell
# Start Ollama in background:
Start-Process ollama serve
# Wait 5 seconds, then restart Streamlit
```

### "FastAPI not running"
```powershell
# Check if port 8000 is in use:
Get-NetTCPConnection -LocalPort 8000

# If in use, stop the process or use different port:
python -m uvicorn src.vendor_api:app --port 8001
# Then update VENDOR_API_BASE in super_agent.py
```

### "SQLite database locked"
```powershell
# Delete existing database and reinit:
Remove-Item data/grocery_agent.db -Force
python src/db_init.py
```

### "Streamlit slow to start"
```powershell
# Clear Streamlit cache:
streamlit run src/app.py --logger.level=error
```

## Performance Notes

- **First run**: 30-60 seconds (LLM inference + all vendor APIs)
- **Subsequent runs**: 10-20 seconds (cached model)
- **Memory usage**: ~500MB-1GB (Ollama + agents)
- **Database**: ~100KB (CSV + metadata)

## Example Sessions

### Session 1: Basic Grocery Shopping
```
Input: "2kg atta, 1L oil, 500g ghee"
Result: 3 items, ₹850 total
Execution time: 45 seconds
```

### Session 2: Budget-Conscious Shopping
```
Input: "5kg rice (budget), 2L milk (any brand), 100g spices"
Result: 3 items, ₹420 total
Agent selected best value options
```

### Session 3: Brand-Specific Shopping
```
Input: "Amul paneer 200g, Mother Dairy ghee 500ml, Aashirvaad atta 5kg"
Result: 3 items from optimal vendors, ₹1250 total
Agent found best prices for specific brands
```

## API Documentation

### GET /api/zepto/search
```
Parameters:
  - product_name (string): Product to search

Response:
{
  "product_name": "basmati_rice",
  "variants": [
    {
      "vendor": "zepto",
      "product_name": "basmati_rice",
      "brand": "india_gate",
      "weight": 500,
      "unit": "g",
      "price": 180,
      "category": "rice",
      "stock_status": "in_stock"
    },
    ...
  ],
  "status": "success"
}
```

### POST /api/search-all
```
Parameters:
  - product_name (string): Product to search

Response:
{
  "zepto": { /* response */ },
  "blinkit": { /* response */ },
  "swiggy_instamart": { /* response */ },
  "bigbasket": { /* response */ }
}
```

## Security Considerations

- No authentication (add as needed)
- No rate limiting (add for production)
- Local Ollama (not exposed to internet)
- SQLite only (no sensitive user data)
- All API calls have timeouts

## Future Enhancements

- [ ] Real vendor API integration (vs. database simulation)
- [ ] User authentication and profiles
- [ ] Budget constraints and spend analysis
- [ ] Purchase history and patterns
- [ ] Multi-user sessions
- [ ] Order tracking integration
- [ ] Recommendation system
- [ ] Loyalty program optimization
- [ ] Dietary preference handling
- [ ] Seasonal product suggestions

## License

MIT

## Support

For issues or questions, check the logs:
```powershell
# View recent logs
Get-Content logs/*.log | Select-Object -Last 50

# Enable debug logging
$env:DEBUG=1
streamlit run src/app.py
```

---

**Developed with ❤️ for intelligent grocery shopping**
