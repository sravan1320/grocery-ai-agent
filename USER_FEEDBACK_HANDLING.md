# User Feedback Handling - Complete Guide

## Overview

The Grocery Agent now has a complete **Replanner** system that handles user feedback after the initial cart is built. Users can modify, remove, or recompare items without restarting the entire agent workflow.

## Architecture

### Flow Diagram

```
User creates cart
        ↓
Agent shows cart and asks "Confirm?"
        ↓
User provides feedback
        ├─→ "Confirm" → Checkout ✅
        ├─→ "Change to Zepto" → Modify item
        ├─→ "Remove rice" → Remove item
        ├─→ "Why not Blinkit?" → Recompare item
        └─→ Other question → LLM processes
        ↓
Agent processes feedback and updates cart
        ↓
Agent shows updated cart
        ↓
User can provide more feedback or confirm
```

## Components (New Files & Functions)

### 1. **Replanner Agent** (`src/agents/replanner.py`)

Main agent handling user feedback with 5 core functions:

#### `process_user_feedback(state: AgentState) -> AgentState`
- **Purpose**: Main entry point for handling user input
- **What it does**:
  - Analyzes user feedback using LLM
  - Determines action type (modify/remove/recompare/other)
  - Routes to appropriate handler
  - Saves feedback to database
- **Returns**: Updated agent state

```python
Example:
  User: "Can you change basmati rice to Zepto?"
  Agent analyzes → Determines action: "modify_item"
  Extracts: product="basmati_rice", vendor="zepto"
  Routes to → modify_cart_item()
```

#### `modify_cart_item(state: AgentState, action_params: dict) -> AgentState`
- **Purpose**: Update a cart item
- **Supported modifications**:
  - Change vendor
  - Change brand
  - Change quantity
- **Example usage**:
  ```
  User: "I prefer Zepto for this product"
  Agent: Updates vendor, recalculates price
  Response: "✅ Updated to Zepto - ₹XYZ"
  ```

#### `remove_cart_item(state: AgentState, action_params: dict) -> AgentState`
- **Purpose**: Remove item from cart
- **Behavior**:
  - Finds and removes the item
  - Recalculates cart total
  - Confirms removal to user
- **Example usage**:
  ```
  User: "Remove basmati rice"
  Agent: Removes from cart, updates total
  Response: "✅ Removed basmati rice from cart"
  ```

#### `recompare_product(state: AgentState, action_params: dict) -> AgentState`
- **Purpose**: Provide detailed product comparison
- **What it does**:
  - Re-analyzes the product across all vendors
  - Provides price breakdown
  - Explains why agent chose current option
  - Uses LLM for reasoning
- **Example usage**:
  ```
  User: "Why not Swiggy for rice?"
  Agent: Analyzes Swiggy option
  Response: "Swiggy: ₹325/kg (₹15 more than BigBasket)
             Recommend: BigBasket saves money"
  ```

#### `confirm_checkout(state: AgentState) -> AgentState`
- **Purpose**: Finalize cart for purchase
- **Behavior**:
  - Validates cart has items
  - Generates final order summary
  - Marks cart as ready for checkout
  - Saves to database
- **Example usage**:
  ```
  User: "Confirm"
  Agent: Generates final summary
  Response: "✅ Order Summary
             3 items | ₹1,850 total"
  ```

## How User Feedback Flows Through System

### Example Scenario

**Initial User Input:**
```
"5kg basmati rice, 2L fabric conditioner"
```

**Agent Process:**
1. Parse input → 2 items identified
2. Fetch variants from all vendors
3. Compare prices with LLM
4. Validate decisions
5. Build cart with best options
6. Ask for confirmation

**Agent's Initial Cart:**
```
✅ Your Shopping Cart (₹1650)
• India Gate Basmati 1kg (5x) from BigBasket - ₹310/kg = ₹1550
• Comfort Fabric Conditioner 2L from Zepto - ₹100
```

**User Feedback Scenario 1: RECOMPARE**

```
User: "Why not Zepto for rice? It's closer to me"

Agent (process_user_feedback):
├─ Analyzes user intent → Action: "recompare"
├─ Extracts: product="basmati_rice"
└─ Routes to: recompare_product()

recompare_product():
├─ Gets all rice variants from Zepto
├─ Compares with current choice (BigBasket)
├─ Runs LLM reasoning
└─ Returns detailed analysis

Agent Response:
"📊 **Detailed Comparison for basmati_rice**

Zepto: India Gate 1kg @ ₹320 = ₹1600 (5x)
BigBasket: India Gate 1kg @ ₹310 = ₹1550 (5x)

BigBasket saves ₹50 overall.
Zepto offers faster delivery.

Your current selection: BigBasket (best value)
Would you like to switch to Zepto?"
```

**User Feedback Scenario 2: MODIFY**

```
User: "Actually, change rice to Blinkit instead"

Agent (process_user_feedback):
├─ Analyzes user intent → Action: "modify_item"
├─ Extracts: product="basmati_rice", vendor="blinkit"
└─ Routes to: modify_cart_item()

modify_cart_item():
├─ Finds basmati_rice in cart
├─ Gets Blinkit options for rice
├─ Selects best option (price/weight)
├─ Updates cart: vendor=blinkit, price=₹330/kg
└─ Recalculates total: ₹1650 (was ₹1550)

Agent Response:
"✅ Updated! Now using India Gate from Blinkit - ₹330/kg

Updated Cart (₹1680):
• India Gate Basmati 1kg (5x) from Blinkit - ₹330/kg = ₹1650
• Comfort Fabric Conditioner 2L from Zepto - ₹100"
```

**User Feedback Scenario 3: REMOVE**

```
User: "Remove the fabric conditioner, I'll buy it elsewhere"

Agent (process_user_feedback):
├─ Analyzes user intent → Action: "remove_item"
├─ Extracts: product="fabric_conditioner"
└─ Routes to: remove_cart_item()

remove_cart_item():
├─ Finds fabric_conditioner in cart
├─ Removes it
├─ Recalculates total: ₹1650 (was ₹1750)
└─ Confirms removal

Agent Response:
"✅ Removed 'fabric_conditioner' from cart

Updated Cart (₹1650):
• India Gate Basmati 1kg (5x) from Blinkit - ₹330/kg = ₹1650"
```

**User Feedback Scenario 4: CHECKOUT**

```
User: "This looks good, confirm checkout"

Agent (router):
├─ Detects checkout confirmation
└─ Routes to: confirm_checkout()

confirm_checkout():
├─ Validates cart (not empty) ✓
├─ Generates final summary
├─ Saves to database
└─ Marks complete

Agent Response:
"✅ **Order Summary**

Items: 1
Total: ₹1,650

• India Gate Basmati 1kg (5x) from Blinkit - ₹330/kg = ₹1,650

✅ Ready for checkout!"
```

## Integration with LangGraph

### Router Function (Updated)

The `router()` function in `super_agent.py` now handles feedback:

```python
def router(state: AgentState) -> str:
    # If awaiting input and user responded
    if state.awaiting_user_input and state.user_input:
        # Check for checkout confirmation
        if state.user_input.lower() in ['confirm', 'yes', 'checkout']:
            return "confirm_checkout"
        else:
            # Other feedback (modify/remove/recompare)
            return "process_feedback"
    
    # If awaiting input but no response yet
    if state.awaiting_user_input and not state.user_input:
        return END
    
    # Normal plan execution
    ... (continues with normal flow)
```

### Graph Nodes

Added to LangGraph workflow:

```python
workflow.add_node("process_feedback", process_user_feedback)
workflow.add_node("confirm_checkout", confirm_checkout)
```

### Graph Edges

```python
# After confirmation, route based on feedback type
workflow.add_conditional_edges("ask_confirmation", router)

# Feedback processing routes to next action
workflow.add_conditional_edges("process_feedback", router)

# Checkout leads directly to save
workflow.add_edge("confirm_checkout", "save_memory")
```

## Data Flow

### AgentState Fields Used

```python
class AgentState:
    # Input from user
    user_input: Optional[str]                    # User's feedback
    awaiting_user_input: bool                    # Wait for response?
    
    # Current state
    current_cart: Cart                           # Items to modify
    all_product_variants: Dict[str, List]        # Options available
    
    # History
    decisions_made: List[Dict]                   # Track all decisions
    messages_to_user: List[str]                  # Feedback to user
```

### Database Storage

Replanner saves all interactions:

```sql
-- User feedback stored
INSERT INTO agent_memory (
    session_id,
    memory_type,      -- "user_feedback", "modification", "removal", "recomparison"
    content,          -- JSON with details
    metadata          -- Additional context
)

Example:
{
    "type": "user_feedback",
    "user_input": "Why not Zepto for rice?",
    "action": "recompare",
    "timestamp": "2025-12-25T10:30:00Z"
}
```

## Usage Examples

### From Streamlit UI

```python
# User types in text area
user_feedback = st.text_input("Your feedback?")

if user_feedback:
    # Add to agent state
    state.user_input = user_feedback
    state.awaiting_user_input = False
    
    # Router processes it
    next_node = router(state)
    # "process_feedback" or "confirm_checkout"
    
    # Execute that node
    state = graph.invoke(state)
    
    # Show results to user
    for msg in state.messages_to_user:
        st.write(msg)
    
    # If still awaiting input, show confirmation options
    if state.awaiting_user_input:
        st.info("Awaiting your next action...")
```

### From Python Script

```python
from agents import execute_agent, process_user_feedback
from models import ParsedGroceryList, ParsedGroceryItem

# Create initial grocery list
items = [ParsedGroceryItem(item_name="basmati_rice", quantity=5, unit="kg")]
grocery_list = ParsedGroceryList(items=items, original_input="5kg rice")

# Execute agent (builds cart, asks for confirmation)
state = execute_agent(grocery_list)

# User provides feedback
state.user_input = "Change to Blinkit please"
state.awaiting_user_input = False

# Process feedback
state = process_user_feedback(state)

# Check results
print(f"New cart total: ₹{state.current_cart.total_price}")
print(f"Agent response: {state.messages_to_user[-1]}")
```

## Error Handling

All feedback handlers include try-catch:

```python
try:
    # Process feedback
    ...
except Exception as e:
    logger.error(f"Error: {e}")
    state.messages_to_user.append(f"Error: {str(e)}")
    return state
```

Common error scenarios:
- Product not in cart → "Product not found in cart"
- No variants available → "No alternate options available"
- Invalid vendor → "Vendor not available for this product"

## Performance

- **Recompare**: ~2-5 seconds (LLM reasoning)
- **Modify**: <1 second (cart update)
- **Remove**: <1 second (item deletion)
- **Checkout**: <1 second (summary generation)

## Future Enhancements

- [ ] Multi-item modifications (bulk actions)
- [ ] Quantity adjustment
- [ ] Price history tracking
- [ ] Recommendation system based on feedback
- [ ] User preferences learning
- [ ] Budget constraints handling
