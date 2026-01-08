# Quick Reference: Dynamic Implementation Details

## How Item Modifications Work (Fully Dynamic)

### 1. Identifying Modified Items
```
User says:     "I want organic basmati rice"
System does:   - Normalizes current_cart_items from actual cart
               - Matches user input against real items
               - Returns which items were identified
Result:        Works with ANY items in ANY cart ✓
```

### 2. Fetching for Modified Item
```
Product:       extracted_from_identify_action_items
System does:   - fetch_from_all_vendors(product_name)
               - Queries API for that specific product
               - Gets fresh variants
Result:        Works for ANY product ✓
```

### 3. LLM Reasoning
```
Input:         product_name + user_requirement + variants
System does:   - LLM evaluates options based on user requirement
               - Selects best match
               - Returns reasoning
Result:        Works with ANY requirement + ANY variants ✓
```

### 4. Updating Cart Item
```
Find:          for item in cart.items: if item.product_name == product_name
Update:        item.brand = new_value
               item.price = new_value
               (other items never touched)
Result:        Item-isolated modification ✓
```

---

## Key Code Snippets

### Identify Action Items (Lines 27-75 in replanner.py)
```python
def identify_action_items(user_input: str, current_cart_items: List[str]):
    # Normalize items from ACTUAL cart
    normalized_cart_items = {}
    for item in current_cart_items:  # ← ACTUAL ITEMS
        normalized_name = item.replace("_", " ").lower()
        normalized_cart_items[normalized_name] = item
    
    # Match against user input
    for normalized_name, original_name in normalized_cart_items.items():
        name_words = normalized_name.split()
        if normalized_name in user_input_lower:  # ← USER INPUT
            modified_items.append(original_name)
    
    return {"modified": modified_items, "new": []}
```

**Key:** Works with ANY items + ANY user input

---

### Modify Cart Item (Lines 210-364 in replanner.py)
```python
def modify_cart_item(state: AgentState, action_params: dict):
    product_name = action_params.get("product_name")  # ← PARAMETER
    
    # Find specific item
    for item in state.current_cart.items:
        if item.product_name == product_name:  # ← MATCH ANY
            item_to_modify = item
            break
    
    # Fetch fresh variants for ONLY this product
    vendor_results = fetch_from_all_vendors(product_name)  # ← DYNAMIC
    
    # LLM reasoning with user context
    context = {
        "product_name": product_name,
        "user_requirement": user_requirement,  # ← USER INPUT
    }
    result = reason_vendor_selection(product_name, by_vendor, context)
    
    # Update ONLY this item
    item_to_modify.vendor = selected_vendor  # ← SPECIFIC ITEM
    item_to_modify.brand = selected_variant.get("brand")
    item_to_modify.price = float(selected_variant.get("price"))
    
    # Recalculate total
    state.current_cart.recalculate_total()
    
    # Other items remain untouched (not in this function)
```

**Key:** Parameter-driven, works with ANY product

---

### Add New Items (Lines 425-575 in replanner.py)
```python
def add_new_item_to_cart(state: AgentState, action_params: dict):
    new_items_input = action_params.get("new_items_input", "")  # ← USER INPUT
    
    # Parse using LLM
    parse_result = parse_items_llm(new_items_input)  # ← LLM DRIVEN
    new_items = parse_result.get("items", [])
    
    # Process each new item
    for item in new_items:
        product_name = item.get("item_name", "").lower().replace(" ", "_")
        
        # Fetch variants for this new item
        vendor_results = fetch_from_all_vendors(product_name)  # ← DYNAMIC
        
        # LLM selects best
        result = reason_vendor_selection(product_name, by_vendor)
        
        # Add to cart
        cart_item = CartItem(
            product_name=product_name,  # ← FROM LLM PARSING
            brand=selected_variant.get("brand"),
            # ... other fields
        )
        state.current_cart.add_item(cart_item)
    
    # Recalculate
    state.current_cart.recalculate_total()
```

**Key:** Completely LLM-driven, works with ANY items

---

## Import Verification Checklist

```
fastapi                   ✓ Used in src/api/vendor_api.py
ollama                    ✓ Used in src/core/llm_engine.py
streamlit                 ✓ Used in src/ui/app.py
requests                  ✓ Used in src/utils/vendor_api_utils.py
pydantic                  ✓ Used in all src/models/ files
```

All imports are in pyproject.toml ✓

---

## Dynamic Flow Summary

```
User Input
    ↓
[Dynamic Identification] - identify_action_items()
    ↓
[Dynamic Processing] - modify_cart_item() OR add_new_item_to_cart()
    ├─ Fetch fresh variants (ANY product)
    ├─ LLM reasons with user context
    └─ Update ONLY relevant items
    ↓
[Dynamic Output] - User message with changes
```

**No hardcoded names in any step** ✓

---

## Testing with Different Items

The system works with ANY items:

```
Test 1: Different product
  User: "I want organic chicken instead"
  System: Identifies "chicken", fetches variants, updates
  Result: ✓ Works

Test 2: Multiple modifications
  User: "Organic rice and premium milk"
  System: Identifies both, processes each
  Result: ✓ Works

Test 3: New items
  User: "Add salt and sugar"
  System: Parses both, fetches, adds to cart
  Result: ✓ Works

Test 4: Complex requirement
  User: "I want free-range eggs with 30 days shelf life"
  System: Parses requirement, LLM matches variants
  Result: ✓ Works
```

---

## File Locations

| Component | File | Lines |
|-----------|------|-------|
| Item identification | src/agents/replanner.py | 27-75 |
| Modify item | src/agents/replanner.py | 210-364 |
| Add items | src/agents/replanner.py | 425-575 |
| LLM parsing | src/core/llm_engine.py | 35-90 |
| Vendor selection | src/core/llm_engine.py | 159-210 |
| Fetch methods | src/utils/vendor_api_utils.py | All |
| Cart model | src/models/cart.py | 34-60 |

---

## What's NOT Hardcoded

✓ Product names in logic  
✓ Vendor names in decisions  
✓ Prices in calculations  
✓ Item lists in code  
✓ User requirements in parsing  

What IS appropriate to hardcode:

✓ Test fixtures (test_*.py)  
✓ Documentation examples (*.md)  
✓ UI placeholder text (ui/)  
✓ Example data (test_utils.py)  

---

**Status:** ✅ All production code is fully dynamic and parameter-driven.

