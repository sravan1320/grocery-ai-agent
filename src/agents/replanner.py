"""
Replanner agent - handles user feedback and dynamic re-planning.
Processes user modifications, deletions, and queries after initial cart creation.
"""
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple

from models.state import AgentState
from core.llm_engine import (
    handle_user_query, 
    reason_vendor_selection
)
from core.db import get_db_connection
from utils.memory_utils import save_memory
from utils.vendor_api_utils import fetch_from_all_vendors, fetch_from_zepto, fetch_from_blinkit, fetch_from_swiggy, fetch_from_bigbasket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def extract_quantity_from_text(text: str):
    """
    Extract quantity + unit from user text.
    Supports:
    - 1kg, 2 kg
    - 500g, 500 g
    - 0.5kg
    Returns: (quantity: float, unit: str) or (None, None)
    """
    text = text.lower().strip()

    match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g)", text)
    if not match:
        return None, None

    qty = float(match.group(1))
    unit = match.group(2)

    # Normalize grams → kg
    if unit == "g":
        qty = qty / 1000
        unit = "kg"

    return qty, unit


def identify_action_items(user_input: str, current_cart_items: List[str]) -> Dict[str, List[str]]:
    """
    Parse user input to identify which items are being modified vs added as new.
    
    Returns:
        {
            "modified": ["basmati_rice"],  # Items already in cart being modified
            "new": ["fabric_softener"]      # New items to add
        }
    """
    logger.info(f"[REPLANNER] Identifying action items from user input: {user_input}")
    
    # Use LLM to identify which items user is referring to
    modified_items = []
    
    user_input_lower = user_input.lower()
    logger.info(f"[REPLANNER] user_input_lower: {user_input_lower}")
    
    # Normalize current cart items for comparison (convert underscores to spaces)
    normalized_cart_items = {}
    for item in current_cart_items:
        # Create mapping: normalized name -> original name
        normalized_name = item.replace("_", " ").lower()
        normalized_cart_items[normalized_name] = item
    logger.info(f"[REPLANNER] normalized_cart_items: {normalized_cart_items}")
    # Check for existing cart items mentioned in user input
    for normalized_name, original_name in normalized_cart_items.items():
        # Check if any part of the normalized name appears in user input
        # Also check word-by-word for better matching
        name_words = normalized_name.split()
        
        # Full phrase match (e.g., "basmati rice" in input)
        if normalized_name in user_input_lower:
            modified_items.append(original_name)
            logger.info(f"[REPLANNER] Identified modification: {original_name}")
            continue
        
        # Individual word match (e.g., "rice" or "basmati" in input)
        matched_words = [word for word in name_words if word in user_input_lower]
        if matched_words and len(matched_words) >= 1:  # Match if any significant word found
            # For phrases like "basmati rice", we want both words to be significant
            # But single-word items should match on their one word
            if len(name_words) == 1 or len(matched_words) >= max(1, len(name_words) - 1):
                modified_items.append(original_name)
                logger.info(f"[REPLANNER] Identified modification: {original_name}")
    
    # If user mentions adding/including new items (but doesn't match existing cart)
    # This is typically caught by the action routing logic
    # For now, new items are handled separately by action == "add_item"
    logger.info(f"[REPLANNER] Final modified items: {modified_items}")
    return {
        "modified": modified_items,
        "new": []
    }


def process_user_feedback(state: AgentState) -> AgentState:
    """
    Process user feedback and determine action needed.
    Analyzes user input and routes to appropriate handler with context awareness.
    
    Smart routing:
    - If user modifies an existing item: targeted replan for ONLY that item
    - If user adds new items: fetch and plan for ONLY those items
    - Other items remain untouched
    """
    logger.info(f"[REPLANNER] Processing user feedback for session {state.session_id}")
    
    try:
        if not state.user_input:
            logger.warning("[REPLANNER] No user input received")
            return state
        
        # Get current cart item names
        current_cart_items = [item.product_name for item in state.current_cart.items]
        
        # Identify which items are being modified vs added as new
        action_items = identify_action_items(state.user_input, current_cart_items)
        logger.info(f"[REPLANNER] Action items identified: {action_items}")
        modified_items = action_items.get("modified", [])
        
        logger.info(f"[REPLANNER] Modified items identified: {modified_items}")
        
        # Get context for LLM to understand
        context = {
            "current_cart": [
                {
                    "product": item.product_name,
                    "brand": item.brand,
                    "vendor": item.vendor,
                    "price": item.price,
                    "quantity": item.display_quantity,
                    "reason": item.decision_reason
                }
                for item in state.current_cart.items
            ],
            "total_price": state.current_cart.total_price,
            "user_input": state.user_input,
            "modified_items": modified_items  # Pass identified modified items to LLM
        }
        logger.info(f"[REPLANNER] Context for LLM: {context}")
        # Use LLM to understand user's intent
        feedback_result = handle_user_query(state.user_input, context)
        logger.info(f"[REPLANNER] LLM feedback result: {feedback_result}")
        if not feedback_result:
            logger.error("[REPLANNER] Failed to process user query")
            state.messages_to_user.append("Sorry, I couldn't understand your request. Please try again.")
            return state
                
        allowed_actions = {"modify_item", "remove_item", "add_item", "recompare", "none"}
        action = feedback_result.get("action", "none")
        logger.info(f"[REPLANNER] Raw action from LLM: {action}")
        if action not in allowed_actions:
            action = "none"
        
        response = feedback_result.get("response", "")
        action_params = feedback_result.get("action_parameters", {})
        
        # 🔥 NOW extract quantity (AFTER action_params exists)
        qty, unit = extract_quantity_from_text(state.user_input)

        if qty is not None and modified_items:
            action_params["product_name"] = modified_items[0]
            action_params["new_quantity"] = qty
            action_params["unit"] = unit

            logger.info(
                f"[REPLANNER] Parsed quantity change: {modified_items[0]} → {qty}{unit}"
            )
        
        # 🔥 Extract additional items from user input manually
        if "add" in state.user_input.lower():
            parts = state.user_input.lower().split("add", 1)
            if len(parts) > 1:
                extras = parts[1]
                action_params["additional_items"] = [
                    i.strip().replace(" ", "_")
                    for i in extras.split(",")
                    if i.strip()
                ]
        # 🔥 HARD OVERRIDE ACTION IF USER CLEARLY MODIFIES CART
        if modified_items:
            action = "modify_item"
            logger.info("[REPLANNER] Overriding action to modify_item based on detected modified_items")

        # 🔥 HARD OVERRIDE ADD IF ADDITIONAL ITEMS EXIST
        elif action_params.get("additional_items"):
            action = "add_item"
            logger.info("[REPLANNER] Overriding action to add_item based on additional_items")

        logger.info(f"[REPLANNER] User intent: {action}")
        logger.info(f"[REPLANNER] LLM Response: {response}")
        
        # Add LLM's response to user
        state.messages_to_user.append(response)
        
        # ===== SMART ENHANCEMENT: Add user requirement to action_params =====
        # This allows modify_cart_item to understand what the user wants
        if action == "modify_item" and modified_items:
            # Extract product name from params or identified items
            product_name = action_params.get("product_name")
            if not product_name and modified_items:
                # If LLM didn't identify product, use our identified one
                product_name = modified_items[0]
                action_params["product_name"] = product_name
            
            # Add the raw user requirement for LLM context
            action_params["user_requirement"] = state.user_input
            
            logger.info(f"[REPLANNER] Enhanced modify_item params with user_requirement: {state.user_input}")
        
        # Store feedback in decisions
        state.decisions_made.append({
            "type": "user_feedback",
            "timestamp": datetime.utcnow().isoformat(),
            "user_input": state.user_input,
            "action": action,
            "parameters": action_params,
            "identified_modified_items": modified_items
        })
        
        # Save to memory
        save_memory(
            state.session_id,
            "user_feedback",
            json.dumps({
                "input": state.user_input,
                "action": action,
                "response": response,
                "modified_items": modified_items
            })
        )
        
        try:
            logger.info(f"[REPLANNER] Routing action: {action} with params: {action_params}")
            # Route to appropriate handler
            if action == "modify_item":
                logger.info("[REPLANNER] Routing to modify_item handler with smart context")
                return modify_cart_item(state, action_params)
            
            elif action == "remove_item":
                logger.info("[REPLANNER] Routing to remove_item handler")
                return remove_cart_item(state, action_params)
            
            elif action == "add_item":
                logger.info("[REPLANNER] Routing to add_item handler")
                return add_new_item_to_cart(state, action_params)
            
            elif action == "recompare":
                logger.info("[REPLANNER] Routing to recompare handler")
                return recompare_product(state, action_params)
            else:
                logger.info("[REPLANNER] No action needed, awaiting further input")
                return state
        finally:
            # 🔒 ALWAYS consume user input (prevents infinite loop)
            state.user_input = None
            state.awaiting_user_input = True
            state.processing_feedback = False
    
    except Exception as e:
        logger.error(f"[REPLANNER] Error: {e}", exc_info=True)
        state.messages_to_user.append(f"Error processing your request: {str(e)}")
        
        return state


def modify_cart_item(state: AgentState, action_params: dict) -> AgentState:
    """
    Modify a cart item with intelligent replanning.
    
    When user modifies an item (e.g., "I want organic basmati rice instead"):
    1. Fetch fresh variants for ONLY that product from all vendors
    2. Use LLM to reason and select best option matching user's requirement
    3. Update only that item in cart
    4. Leave other items untouched
    """
    logger.info(f"[REPLANNER-MODIFY] Modifying cart item with smart replanning: {action_params}")
    
    try:
        from models.cart import CartItem
        
        product_name = action_params.get("product_name")
        modification = action_params.get("modification", {})
        user_requirement = action_params.get("user_requirement", "")  # e.g., "organic type"
        
        if not product_name:
            logger.warning("[REPLANNER-MODIFY] No product_name specified")
            state.messages_to_user.append("Please specify which product to modify.")
            return state
        
        # Find item in cart
        item_to_modify = None
        for item in state.current_cart.items:
            if item.product_name == product_name:
                item_to_modify = item
                break
        
        if not item_to_modify:
            logger.warning(f"[REPLANNER-MODIFY] Product {product_name} not found in cart")
            state.messages_to_user.append(f"Product '{product_name}' not found in cart.")
            return state
        
        logger.info(f"[REPLANNER-MODIFY] Starting full replanning for {product_name}")
        logger.info(f"[REPLANNER-MODIFY] User requirement: {user_requirement}")
        
        # ===== STEP 1: Fetch FRESH variants for ONLY this product =====
        logger.info(f"[REPLANNER-MODIFY] Fetching fresh variants from all vendors for {product_name}")
        
        vendor_results = fetch_from_all_vendors(product_name)
        
        # Aggregate fresh variants
        fresh_variants = []
        successful_vendors = []
        
        for vendor_name, vendor_response in vendor_results.items():
            if vendor_response and vendor_response.variants:
                fresh_variants.extend(vendor_response.variants)
                successful_vendors.append(vendor_name)
                logger.info(f"[REPLANNER-MODIFY] Got {len(vendor_response.variants)} variants from {vendor_name}")
        
        if not fresh_variants:
            logger.warning(f"[REPLANNER-MODIFY] No fresh variants found for {product_name}")
            state.messages_to_user.append(
                f"⚠️ Could not find fresh options for '{product_name}'. Keeping current selection."
            )
            return state
        
        logger.info(f"[REPLANNER-MODIFY] Total fresh variants available: {len(fresh_variants)}")
        
        # ===== STEP 2: Update state with fresh variants =====
        state.all_product_variants[product_name] = fresh_variants
        
        # ===== STEP 3: Group by vendor for LLM reasoning =====
        by_vendor = {}
        for v in fresh_variants:
            if v.vendor not in by_vendor:
                by_vendor[v.vendor] = []
            by_vendor[v.vendor].append(v)
        
        logger.info(f"[REPLANNER-MODIFY] Grouped variants by vendor: {list(by_vendor.keys())}")
        
        # ===== STEP 4: Use LLM to select best option WITH user requirement context =====
        context_for_llm = {
            "product_name": product_name,
            "user_requirement": user_requirement,
            "modification_details": modification,
            "current_selection": {
                "brand": item_to_modify.brand,
                "vendor": item_to_modify.vendor,
                "price": item_to_modify.price
            }
        }
        
        logger.info(f"[REPLANNER-MODIFY] Running LLM reasoning with user context: {context_for_llm}")
        result = reason_vendor_selection(product_name, by_vendor, context=context_for_llm)
        
        if not result:
            logger.warning("[REPLANNER-MODIFY] LLM reasoning failed")
            state.messages_to_user.append(
                f"⚠️ Could not process your modification. Please try again."
            )
            return state
        
        # ===== STEP 5: Update ONLY this item in cart =====
        selected_variant = result.get("selected_variant", {})
        selected_vendor = result.get("selected_vendor", "")
        reasoning = result.get("reasoning", "Best matching option for your requirement")
        
        logger.info(f"[REPLANNER-MODIFY] Selected: {selected_variant.get('brand')} from {selected_vendor}")
        
        new_qty = action_params.get("new_quantity")

        if new_qty:
            item_to_modify.display_quantity = float(new_qty)
            # 🔥 infer correct unit from quantity
            item_to_modify.display_unit = "kg" if float(new_qty) >= 1 else "g"

        item_to_modify.vendor = selected_vendor
        item_to_modify.brand = selected_variant.get("brand", item_to_modify.brand)
        item_to_modify.price = float(selected_variant.get("price", item_to_modify.price))

        item_to_modify.decision_reason = f"Modified: {reasoning}"
        # item_to_modify.selected_at = datetime.utcnow()
        
        # ===== STEP 5.5: HANDLE ADDITIONAL ITEMS =====
        additional_items = action_params.get("additional_items", [])

        if additional_items:
            logger.info(
                f"[REPLANNER-MODIFY] Processing additional items: {additional_items}"
            )

            # Prevent reprocessing existing items
            existing_products = {item.product_name for item in state.current_cart.items}

            for new_item in additional_items:
                product_name_new = new_item.lower().replace(" ", "_")

                if product_name_new in existing_products:
                    logger.info(
                        f"[REPLANNER-MODIFY] Skipping {product_name_new} (already in cart)"
                    )
                    continue

                # 🔁 Reuse ADD logic safely
                add_new_item_to_cart(
                    state,
                    {"new_items_input": product_name_new}
                )

        
        # ===== STEP 6: Update cart total (other items unchanged) =====
        state.current_cart.recalculate_total()
        
        # ===== STEP 7: Notify user =====
        message = (
            f"✅ Updated '{product_name}'!\n\n"
            f"**New Selection**: {selected_variant.get('brand')} "
            f"({item_to_modify.display_quantity}{item_to_modify.display_unit}) "
            f"from {selected_vendor.upper()}\n"
            f"**Price**: ₹{selected_variant.get('price')}\n"
            f"**Reason**: {reasoning}\n\n"
            f"**Updated Cart Total**: ₹{state.current_cart.total_price:.2f}"
        )
        state.messages_to_user.append(message)
        logger.info(f"[REPLANNER-MODIFY] User notified of modification - {message}")
        # ===== STEP 8: Save to memory =====
        save_memory(
            state.session_id,
            "targeted_modification",
            json.dumps({
                "product": product_name,
                "user_requirement": user_requirement,
                "modification": modification,
                "old_selection": {
                    "brand": item_to_modify.brand,
                    "vendor": item_to_modify.vendor,
                    "price": float(item_to_modify.price)
                },
                "new_selection": {
                    "brand": selected_variant.get("brand"),
                    "vendor": selected_vendor,
                    "price": float(selected_variant.get("price", 0))
                },
                "reasoning": reasoning,
                "cart_total_after": state.current_cart.total_price,
                "timestamp": datetime.utcnow().isoformat()
            })
        )        
        logger.info(
            f"[REPLANNER-MODIFY] Successfully modified {product_name} - cart total: ₹{state.current_cart.total_price:.2f}"
        )
        
        # ✅ Only ask for confirmation again, NEVER rebuild cart
        for step in state.execution_plan.steps:
            if step.action == "ask_confirmation":
                step.status = "pending"

        # Reset user input for next interaction
        state.user_input = None
        state.awaiting_user_input = True
        state.processing_feedback = False

        return state
    
    except Exception as e:
        logger.error(f"[REPLANNER-MODIFY] Error: {e}", exc_info=True)
        state.messages_to_user.append(f"Error modifying item: {str(e)}")
        return state


def remove_cart_item(state: AgentState, action_params: dict) -> AgentState:
    """
    Remove an item from the shopping cart.
    """
    logger.info(f"[REPLANNER-REMOVE] Removing cart item with params: {action_params}")
    
    try:
        product_name = action_params.get("product_name")
        
        if not product_name:
            logger.warning("[REPLANNER-REMOVE] No product_name specified")
            state.messages_to_user.append("Please specify which product to remove.")
            return state
        
        # Find and remove item
        removed = False
        for i, item in enumerate(state.current_cart.items):
            if item.product_name == product_name:
                state.current_cart.items.pop(i)
                removed = True
                state.messages_to_user.append(f"✅ Removed '{product_name}' from cart.")
                logger.info(f"[REPLANNER-REMOVE] Removed {product_name}")
                break
        
        if not removed:
            state.messages_to_user.append(f"Product '{product_name}' not found in cart.")
            return state
        
        # Update cart total
        state.current_cart.recalculate_total()
        
        # Save removal to memory
        save_memory(
            state.session_id,
            "removal",
            json.dumps({
                "product": product_name,
                "cart_total_after": state.current_cart.total_price,
                "items_remaining": len(state.current_cart.items)
            })
        )
        
        logger.info("[REPLANNER-REMOVE] Item removed successfully")
        
        # Reset user input for next interaction
        state.user_input = None
        state.awaiting_user_input = True
        state.processing_feedback = False

        return state
    
    except Exception as e:
        logger.error(f"[REPLANNER-REMOVE] Error: {e}")
        state.messages_to_user.append(f"Error removing item: {str(e)}")
        return state


def add_new_item_to_cart(state: AgentState, action_params: dict) -> AgentState:
    """
    Add new items to existing cart without clearing previous items.
    Fetches variants for new products and adds them intelligently.
    Only processes items that are NOT already in the cart.
    """
    logger.info(f"[REPLANNER-ADD] Adding new items with params: {action_params}")
    
    try:
        from core.llm_engine import parse_grocery_list_llm as parse_items_llm
        from models.cart import CartItem
        
        new_items_input = action_params.get("new_items_input", "")
        
        if not new_items_input:
            logger.warning("[REPLANNER-ADD] No new items specified")
            state.messages_to_user.append("Please specify which items to add.")
            return state
        
        # Parse new items using LLM
        logger.info(f"[REPLANNER-ADD] Parsing new items using LLM: {new_items_input}")
        
        parse_result = parse_items_llm(new_items_input)
        
        if not parse_result:
            logger.warning("[REPLANNER-ADD] LLM parsing failed")
            state.messages_to_user.append("Could not parse new items. Please try: '1kg sugar, 500g tea'")
            return state
        
        new_items = parse_result.get("items", [])
        
        if not new_items:
            state.messages_to_user.append("Could not parse new items. Please try: '1kg sugar, 500g tea'")
            return state
        
        logger.info(f"[REPLANNER-ADD] Parsed {len(new_items)} new items: {[item.get('item_name') for item in new_items]}")
        
        # Get currently confirmed items in cart
        confirmed_items = {item.product_name for item in state.current_cart.items}
        logger.info(f"[REPLANNER-ADD] Currently in cart: {confirmed_items}")
        
        # Fetch variants for each NEW item (not already in cart)
        new_variants = {}
        for item in new_items:
            product_name = item.get("item_name", "").lower().replace(" ", "_")
            
            if product_name in {i.product_name for i in state.current_cart.items}:
                logger.info(f"[REPLANNER-ADD] {product_name} already exists, skipping")
                continue
            
            # Skip if already in cart
            if product_name in confirmed_items:
                logger.info(f"[REPLANNER-ADD] Skipping {product_name} - already in cart")
                continue
            
            logger.info(f"[REPLANNER-ADD] Fetching variants for NEW item: {product_name}")
            
            # Use centralized fetch_from_all_vendors
            vendor_results = fetch_from_all_vendors(product_name)
            
            variants_for_product = []
            successful_vendors = []
            
            for vendor_name, vendor_response in vendor_results.items():
                if vendor_response and vendor_response.variants:
                    variants_for_product.extend(vendor_response.variants)
                    successful_vendors.append(vendor_name)
            
            if not variants_for_product:
                logger.warning(f"[REPLANNER-ADD] No variants found for {product_name}")
                state.messages_to_user.append(f"⚠️ Could not find '{product_name}' in any vendor")
                continue
            
            new_variants[product_name] = variants_for_product
            logger.info(f"[REPLANNER-ADD] Found {len(variants_for_product)} variants for {product_name} from {successful_vendors}")
        
        # Update state with new variants
        state.all_product_variants.update(new_variants)
        
        # Use LLM to select best options for new items
        items_added = 0
        for item in new_items:
            product_name = item.get("item_name", "").lower().replace(" ", "_")
            quantity = float(item.get("quantity", 1))
            unit = item.get("unit", "pieces")
            
            # Skip if already in cart
            if product_name in confirmed_items:
                continue
            
            variants = new_variants.get(product_name, [])
            
            if not variants:
                logger.warning(f"[REPLANNER-ADD] Skipping {product_name} - no variants found")
                continue
            
            # Group by vendor
            by_vendor = {}
            for v in variants:
                if v.vendor not in by_vendor:
                    by_vendor[v.vendor] = []
                by_vendor[v.vendor].append(v)
            
            # Use LLM reasoning
            result = reason_vendor_selection(product_name, by_vendor)
            
            if result:
                selected_variant = result.get("selected_variant", {})
                selected_vendor = result.get("selected_vendor", "")
                
                # Add to cart
                cart_item = CartItem(
                    product_name=product_name,
                    brand=selected_variant.get("brand", ""),
                    weight=float(selected_variant.get("weight", 0)),
                    unit=selected_variant.get("unit", ""),
                    vendor=selected_vendor,
                    price=float(selected_variant.get("price", 0)),
                    quantity=float(quantity),
                    decision_reason=f"Added by user: {result.get('reasoning', 'Best value option')}",
                    # price_per_unit=float(selected_variant.get("price", 0)) / max(float(selected_variant.get("weight", 1)), 1)
                    display_quantity=float(selected_variant.get("display_quantity",0)),
                    display_unit=selected_variant.get("display_unit","")
                )
                
                state.current_cart.add_item(cart_item)
                items_added += 1
                
                logger.info(f"[REPLANNER-ADD] Added {product_name} from {selected_vendor} to cart")
        
        # Update cart total
        state.current_cart.recalculate_total()
        
        # Confirm to user
        if items_added > 0:
            state.messages_to_user.append(f"✅ Added {items_added} new item(s) to cart!\n\nUpdated Cart Total: ₹{state.current_cart.total_price:.2f}")
        else:
            state.messages_to_user.append("Could not add any new items. Please try again with different products.")
        
        # Save to memory
        save_memory(
            state.session_id,
            "item_addition",
            json.dumps({
                "items_added": items_added,
                "new_items_requested": [item.get("item_name") for item in new_items],
                "new_cart_total": state.current_cart.total_price,
                "total_items_in_cart": len(state.current_cart.items),
                "timestamp": datetime.utcnow().isoformat()
            })
        )
        
        logger.info(f"[REPLANNER-ADD] Addition complete - {items_added} items added")
        # Reset user input for next interaction
        state.user_input = None
        state.awaiting_user_input = True
        state.processing_feedback = False

        return state
    
    except Exception as e:
        logger.error(f"[REPLANNER-ADD] Error: {e}", exc_info=True)
        state.messages_to_user.append(f"Error adding items: {str(e)}")
        return state


def recompare_product(state: AgentState, action_params: dict) -> AgentState:
    """
    Re-analyze a specific product and provide updated recommendations.
    User might want to know: "Why not vendor X?", "Can you find cheaper option?", etc.
    """
    logger.info(f"[REPLANNER-RECOMPARE] Recomparing product with params: {action_params}")
    
    try:
        product_name = action_params.get("product_name")
        question = action_params.get("question", "")
        
        if not product_name:
            logger.warning("[REPLANNER-RECOMPARE] No product_name specified")
            state.messages_to_user.append("Please specify which product to recompare.")
            return state
        
        # Get all variants for this product
        available_variants = state.all_product_variants.get(product_name, [])
        
        if not available_variants:
            logger.warning(f"[REPLANNER-RECOMPARE] No variants found for {product_name}")
            state.messages_to_user.append(f"No variants found for '{product_name}'.")
            return state
        
        # Group by vendor
        by_vendor = {}
        for v in available_variants:
            if v.vendor not in by_vendor:
                by_vendor[v.vendor] = []
            by_vendor[v.vendor].append(v)
        
        # Use LLM to provide detailed comparison
        result = reason_vendor_selection(product_name, by_vendor)
        
        if result:
            comparison_summary = f"""
📊 **Detailed Comparison for {product_name}**

{result.get('reasoning', 'N/A')}

**Best Value**: {result.get('selected_vendor', 'N/A').upper()}
**Brand**: {result.get('selected_variant', {}).get('brand', 'N/A')}
**Price**: ₹{result.get('selected_variant', {}).get('price', 'N/A')}
**Confidence**: {result.get('confidence', 0):.0%}

{result.get('vendor_analysis', 'N/A')}
"""
            state.messages_to_user.append(comparison_summary)
            
            logger.info("[REPLANNER-RECOMPARE] Recomparison provided")
        else:
            state.messages_to_user.append("Could not generate detailed comparison.")
        
        # Save recomparison to memory
        save_memory(
            state.session_id,
            "recomparison",
            json.dumps({
                "product": product_name,
                "user_question": question,
                "result": result
            })
        )
        
        return state
    
    except Exception as e:
        logger.error(f"[REPLANNER-RECOMPARE] Error: {e}")
        state.messages_to_user.append(f"Error recomparing product: {str(e)}")
        return state


def confirm_checkout(state: AgentState) -> AgentState:
    """
    Finalize the shopping cart and prepare for checkout.
    """
    logger.info(f"[REPLANNER-CHECKOUT] Finalizing checkout for session {state.session_id}")
    
    try:
        if not state.current_cart.items:
            state.messages_to_user.append("⚠️ Your cart is empty. Please add items before checkout.")
            return state
        
        # Generate final summary
        checkout_summary = f"""
        ✅ **Order Summary**

        Items: {len(state.current_cart.items)}
        Total: ₹{state.current_cart.total_price:.2f}

        **Items:**
        """
        for item in state.current_cart.items:
            checkout_summary += f"• {item.brand} {item.weight}{item.unit} from {item.vendor.upper()} - ₹{item.price}\n"
        
        checkout_summary += "\n✅ Ready for checkout!"
        
        state.messages_to_user.append(checkout_summary)
        
        # Save final cart to memory
        save_memory(
            state.session_id,
            "checkout",
            json.dumps({
                "items": len(state.current_cart.items),
                "total_price": state.current_cart.total_price,
                "timestamp": datetime.utcnow().isoformat()
            })
        )
        
        state.user_input = None
        state.processing_feedback = False
        state.awaiting_user_input = False

        logger.info("[REPLANNER-CHECKOUT] Checkout finalized")
        
        return state
    
    except Exception as e:
        logger.error(f"[REPLANNER-CHECKOUT] Error: {e}")
        state.messages_to_user.append(f"Error finalizing checkout: {str(e)}")
        return state
