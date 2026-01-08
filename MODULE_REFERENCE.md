# 🎯 Module Reference Guide

## Quick Navigation

### 🤖 agents/ - AI Decision Making
Where the autonomous agent logic lives.

**planner.py**
- `create_execution_plan()` - Creates execution plans
- Decides what steps are needed

**executor.py**
- `parse_grocery_list()` - Parse user input
- `fetch_product_variants()` - Fetch from vendors
- `compare_and_rank_products()` - Compare options
- `assemble_shopping_cart()` - Build shopping cart
- Functions to fetch from each vendor (zepto, blinkit, swiggy, bigbasket)

**observer.py**
- `apply_llm_reasoning()` - LLM decision making
- `validate_cart_decisions()` - Validate decisions
- `request_user_confirmation()` - Get user confirmation
- `persist_session_memory()` - Save to database

**replanner.py** (NEW - User Feedback Handling)
- `process_user_feedback()` - Analyze user input and route to handler
- `modify_cart_item()` - Change vendor/brand/quantity
- `remove_cart_item()` - Remove item from cart
- `recompare_product()` - Re-analyze product with detailed comparison
- `confirm_checkout()` - Finalize cart for purchase

**super_agent.py**
- `execute_agent()` - Main entry point
- `build_super_agent_graph()` - Build LangGraph
- `router()` - Dynamic routing logic (handles feedback flow)

---

### 🌐 api/ - REST API Layer
External vendor API simulation.

**vendor_api.py**
- `GET /health` - Health check
- `GET /api/zepto/search` - Search Zepto
- `GET /api/blinkit/search` - Search Blinkit
- `GET /api/swiggy_instamart/search` - Search Swiggy
- `GET /api/bigbasket/search` - Search BigBasket
- `GET /api/search-all` - Search all vendors
- `GET /api/stats` - Get statistics

---

### 📊 models/ - Data Schemas
Pydantic models for type validation.

**product.py**
- `ProductVariant` - Product from vendor
- `PriceComparison` - Price comparison

**grocery_list.py**
- `ParsedGroceryItem` - Single grocery item
- `ParsedGroceryList` - Complete list

**cart.py**
- `CartItem` - Item in shopping cart
- `Cart` - Full shopping cart

**plan.py**
- `PlanningStep` - Single execution step
- `ExecutionPlan` - Full execution plan

**state.py**
- `LLMReasoningInput` - Input to LLM
- `LLMReasoningOutput` - Output from LLM
- `AgentState` - Agent's current state
- `AgentMemoryEntry` - Persistent memory

**api.py**
- `VendorAPIResponse` - API response
- `APIError` - Error response

---

### 🔧 core/ - Infrastructure
Core utilities and integrations.

**llm_engine.py**
- `parse_grocery_list()` - Parse user input with LLM
- `compare_product_variants()` - Compare variants
- `reason_vendor_selection()` - Choose best vendor
- `handle_user_query()` - Handle user questions
- `validate_llm_decision()` - Validate LLM output
- `call_ollama()` - Raw Ollama call
- `parse_json_from_llm_output()` - Extract JSON

**retry_utils.py**
- `RetryConfig` - Configure retry behavior
- `retry_with_backoff()` - Decorator for retry
- `TransientError` - Temporary error
- `PermanentError` - Permanent error
- `APIResponseValidator` - Validate responses
- `validate_llm_output()` - Validate LLM output

**db.py**
- `get_db_connection()` - Get DB connection
- `init_database()` - Initialize schema
- `import_csv_data()` - Import CSV

---

### 🎨 ui/ - User Interface
Streamlit web application.

**app.py**
- Shopping Tab - Input grocery list & see results
- Analysis Tab - View execution plan & decisions
- Settings Tab - Health checks & system status

---

### 🛠️ utils/ - Testing Tools
Testing and debugging utilities.

**test_utils.py**
- `test_database()` - Test DB connection
- `test_api_connectivity()` - Test FastAPI
- `test_llm_connectivity()` - Test Ollama
- `run_example_agent()` - Run example
- `health_check()` - Run all checks

---

## Common Usage Patterns

### Run the Agent
```python
from agents import execute_agent
from models import ParsedGroceryList, ParsedGroceryItem

items = [ParsedGroceryItem(item_name="basmati_rice", quantity=5, unit="kg")]
grocery_list = ParsedGroceryList(items=items, original_input="5kg rice")

result = execute_agent(grocery_list)
print(result.current_cart)
```

### Fetch from Vendors
```python
from agents.executor import fetch_from_zepto
response = fetch_from_zepto("basmati_rice")
```

### LLM Reasoning
```python
from core import compare_product_variants

result = compare_product_variants(
    "basmati_rice",
    variants,
    quantity=5,
    unit="kg"
)
```

### Database Operations
```python
from core import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT * FROM products")
```

### Retry with Backoff
```python
from core import retry_with_backoff, RetryConfig

@retry_with_backoff
def my_function():
    pass
```

---

## Dependency Flow

```
User Input (Streamlit UI)
    ↓
agents/super_agent.py::execute_agent()
    ↓
agents/planner.py::create_execution_plan()          [Create plan]
    ↓
agents/executor.py::fetch_product_variants()  [Fetch from api/]
    ↓
api/vendor_api.py (FastAPI endpoints)      [Query database]
    ↓
agents/executor.py::compare_and_rank_products()  [Compare options]
    ↓
core/llm_engine.py (Ollama/Qwen)           [LLM reasoning]
    ↓
agents/observer.py::validate_cart_decisions() [Validation]
    ↓
agents/executor.py::assemble_shopping_cart()      [Build cart]
    ↓
agents/observer.py::request_user_confirmation() [Get approval]
    ↓
╔══════════════════════════════════════════════════╗
║ agents/replanner.py (User Feedback Loop)         ║
║ - process_user_feedback()                        ║
║ - modify_cart_item()                             ║
║ - remove_cart_item()                             ║
║ - recompare_product()                            ║
║ - confirm_checkout()                             ║
╚══════════════════════════════════════════════════╝
    ↓
Result → Back to Streamlit
```

---

## File Organization Tips

**Adding a New Agent?**
→ Create `src/agents/your_agent.py`
→ Import in `src/agents/__init__.py`
→ Add node to `super_agent.py`

**Adding a New Model?**
→ Create `src/models/your_model.py`
→ Import in `src/models/__init__.py`
→ Use in agents/

**Adding a New Vendor?**
→ Add endpoint to `src/api/vendor_api.py`
→ Add fetch function to `src/agents/executor.py`
→ Update router in `src/agents/super_agent.py`

**Adding Tests?**
→ Add function to `src/utils/test_utils.py`
→ Import in `src/utils/__init__.py`

---

## Running Each Component

```bash
# API Server
python -m uvicorn src.api.vendor_api:app --port 8000

# Streamlit UI
streamlit run src/ui/app.py

# Tests
python -c "from src.utils import health_check; health_check()"

# Direct agent execution
python -c "from src.agents import execute_agent; ..."
```

---

## Key Design Patterns

**1. Single Responsibility**
- Each file has ONE job
- planner.py only plans
- executor.py only executes
- observer.py only observes

**2. Clean Imports**
- Each module imports only what it needs
- No circular dependencies
- Clear dependency tree

**3. Pydantic Validation**
- All data validated at boundaries
- Type hints throughout
- Automatic validation

**4. Retry Logic**
- Exponential backoff with jitter
- Classify errors (transient vs permanent)
- Automatic recovery

**5. Persistent Memory**
- SQLite stores decisions
- Session recovery possible
- Learning from past choices

---

## Architecture Highlights

✅ **Dynamic Routing** - Not static DAG, routes at runtime
✅ **LLM-Powered** - Qwen 2.5 7B for intelligent decisions
✅ **Resilient** - Retries with exponential backoff
✅ **Validated** - 4 layers of validation
✅ **Observable** - Full execution plan visibility
✅ **Persistent** - Remembers past decisions
✅ **Modular** - Add features without breaking anything
✅ **Production-Grade** - Error handling, logging, monitoring

---

**Version**: 1.0.0
**Status**: ✅ Production Ready
**Last Updated**: December 25, 2025
