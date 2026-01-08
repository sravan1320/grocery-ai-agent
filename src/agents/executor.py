"""
Executor agents - handle data fetching and processing.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import requests

from models.state import AgentState
from models.api import VendorAPIResponse
from models.cart import CartItem
from core.llm_engine import (
    parse_grocery_list_llm, 
    select_best_variant_by_quantity,
    explain_variant_selection,
    reason_vendor_selection, 
    validate_llm_decision    
)
from core.retry_utils import retry_with_backoff, RetryConfig, APIResponseValidator, TransientError,PermanentError
from core.db import get_db_connection
from utils.memory_utils import save_memory
from utils.vendor_api_utils import fetch_from_all_vendors, fetch_from_zepto, fetch_from_blinkit, fetch_from_swiggy, fetch_from_bigbasket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# API configuration
VENDOR_API_BASE = "http://localhost:8000"
RETRY_CONFIG = RetryConfig(max_retries=3, initial_backoff=1.0, backoff_multiplier=2.0)


def parse_grocery_list(state: AgentState) -> AgentState:
    """
    Parse user's natural language input into structured grocery list.
    Calls LLM to intelligently parse user input.
    
    IMPORTANT: state.user_input MUST be set by the caller before calling this function.
    """
    logger.info(f"[EXECUTOR-PARSE] Parsing grocery list for session {state.session_id}")
    
    try:
        # Find parse step in plan
        parse_step = next(
            (s for s in state.execution_plan.steps if s.action == "parse_list"),
            None
        )
        logger.info(f"[EXECUTOR-PARSE] state.user_input: {state.user_input}")
        logger.info(f"[EXECUTOR-PARSE] state.execution_plan.steps: {[s.action for s in state.execution_plan.steps]}")
        logger.info(f"[EXECUTOR-PARSE] parse_step found: {parse_step is not None}")
                
        if not parse_step:
            logger.error("[EXECUTOR-PARSE] No parse step found in plan")
            raise RuntimeError("Execution plan missing parse_list step")
        
        # Check if user_input is provided
        if not state.user_input:
            logger.error("[EXECUTOR-PARSE] No user input provided in state")
            parse_step.status = "failed"
            parse_step.error = "User input not provided"
            state.messages_to_user.append("❌ Please provide your grocery list.")
            return state
        
        logger.info(f"[EXECUTOR-PARSE] User input: {state.user_input}")
        parse_step.status = "in_progress"
        
        # ===== Call LLM to parse grocery list =====
        logger.info("[EXECUTOR-PARSE] Calling LLM for parsing")
        parse_result = parse_grocery_list_llm(state.user_input)
        
        if not parse_result:
            logger.error("[EXECUTOR-PARSE] LLM parsing failed")
            parse_step.status = "failed"
            parse_step.error = "LLM parsing failed"
            state.messages_to_user.append("❌ Failed to parse your grocery list. Please try again.")
            return state
        
        # Convert parsed result to ParsedGroceryList
        from ..models import ParsedGroceryList, ParsedGroceryItem
        
        items = parse_result.get("items", [])
        parsed_items = [
            ParsedGroceryItem(
                item_name=item.get("item_name", "").lower().replace(" ", "_"),
                quantity=float(item.get("quantity", 1)),
                unit=item.get("unit", "pieces")
            )
            for item in items
        ]
        
        state.user_grocery_list = ParsedGroceryList(
            raw_input=state.user_input,
            items=parsed_items
        )
        
        parse_step.status = "completed"
        parse_step.result = f"Parsed {len(parsed_items)} items"
        
        logger.info(f"[EXECUTOR-PARSE] Successfully parsed {len(parsed_items)} items:")
        for item in parsed_items:
            logger.info(f"  - {item.item_name}: {item.quantity}")
        
        # Save to memory
        save_memory(
            state.session_id,
            "parsing",
            json.dumps({
                "user_input": state.user_input,
                "parsed_items": len(parsed_items),
                "items": [
                    {
                        "item_name": item.item_name,
                        "quantity": item.quantity,
                        "unit": item.unit
                    }
                    for item in parsed_items
                ]
            })
        )
        
        # Notify user
        items_text = "\n".join([f"• {item.quantity}{item.unit} {item.item_name}" for item in parsed_items])
        state.messages_to_user.append(f"✅ Parsed your grocery list:\n{items_text}\n\nFetching best prices from vendors...")
        
        logger.info("[EXECUTOR-PARSE] Parsing complete")
        return state
    
    except Exception as e:
        logger.error(f"[EXECUTOR-PARSE] Error: {e}", exc_info=True)
        parse_step.status = "failed"
        parse_step.error = str(e)
        state.messages_to_user.append(f"❌ Error parsing list: {str(e)}")
        return state


def fetch_product_variants(state: AgentState) -> AgentState:
    """
    Fetch product variants from all vendors.
    Calls multiple vendor APIs with retry logic using centralized utilities.
    """
    logger.info(f"[EXECUTOR-FETCH] Fetching variants for session {state.session_id}")
    
    try:
        if not state.user_grocery_list:
            logger.warning("[EXECUTOR-FETCH] No grocery list to fetch for")
            state.messages_to_user.append("❌ No grocery list provided.")
            return state
        
        # Find fetch steps in plan
        fetch_steps = [s for s in state.execution_plan.steps if s.action == "fetch_variants"]
        
        if not fetch_steps:
            logger.warning("[EXECUTOR-FETCH] No fetch steps in plan")
            return state
        
        for step in fetch_steps:
            step.status = "in_progress"
            product_name = step.parameters.get("product_name")
            
            if not product_name:
                logger.warning("[EXECUTOR-FETCH] No product_name in step")
                step.status = "failed"
                step.error = "No product_name"
                continue
            
            logger.info(f"[EXECUTOR-FETCH] Fetching variants for {product_name}")
            
            # ===== Use centralized fetch_from_all_vendors =====
            vendor_results = fetch_from_all_vendors(product_name)
            logger.info(f"[EXECUTOR-FETCH] Fetched from vendors: {vendor_results}")
            # Aggregate variants
            all_variants = []
            successful_vendors = []
            failed_vendors = []
            
            for vendor_name, vendor_response in vendor_results.items():
                if vendor_response and vendor_response.variants:
                    all_variants.extend(vendor_response.variants)
                    successful_vendors.append(vendor_name)
                    logger.info(f"[EXECUTOR-FETCH] Got {len(vendor_response.variants)} variants from {vendor_name}")
                else:
                    failed_vendors.append(vendor_name)
            
            if not all_variants:
                logger.warning(f"[EXECUTOR-FETCH] No variants found for {product_name} from any vendor")
                step.status = "failed"
                step.error = f"No variants found from any vendor"
                state.messages_to_user.append(f"⚠️ Could not find '{product_name}' in any vendor")
                continue
            
            # Store fetched variants in state
            state.all_product_variants[product_name] = all_variants
            
            step.status = "completed"
            step.result = f"Fetched {len(all_variants)} variants from {len(successful_vendors)} vendors"
            
            logger.info(f"[EXECUTOR-FETCH] {product_name}: {len(all_variants)} total variants from {successful_vendors}")
            
            # Save to memory
            save_memory(
                state.session_id,
                "api_call",
                json.dumps({
                    "product": product_name,
                    "vendors_successful": successful_vendors,
                    "vendors_failed": failed_vendors,
                    "total_variants": len(all_variants),
                    "timestamp": datetime.utcnow().isoformat()
                })
            )
        
        logger.info("[EXECUTOR-FETCH] All fetches complete")
        
        # Notify user if all successful
        if all(step.status == "completed" for step in fetch_steps):
            state.messages_to_user.append("✅ Fetched products from all vendors. Comparing prices...")
        
        return state
    
    except Exception as e:
        logger.error(f"[EXECUTOR-FETCH] Error: {e}", exc_info=True)
        state.messages_to_user.append(f"❌ Error fetching products: {str(e)}")
        return state


def compare_and_rank_products(state: AgentState) -> AgentState:
    """
    Compare product variants and normalize prices.
    Uses LLM for intelligent comparison with validation.
    """
    logger.info(f"[EXECUTOR-COMPARE] Comparing prices for session {state.session_id}")
    
    try:
        compare_step = next(
            (s for s in state.execution_plan.steps if s.action == "compare_prices"),
            None
        )
        
        if not compare_step or not state.all_product_variants:
            return state
        
        compare_step.status = "in_progress"
        
        comparisons = {}
        
        for product_name, variants in state.all_product_variants.items():
            if not variants:
                continue
            
            logger.info(f"[EXECUTOR-COMPARE] Comparing {len(variants)} variants for {product_name}")
            
            # Find user's quantity need
            item = next(
                (i for i in state.user_grocery_list.items if i.item_name == product_name),
                None
            )
            
            if item:                    
                decision = select_best_variant_by_quantity(
                    variants=variants,
                    requested_qty=item.quantity,
                    requested_unit=item.unit
                )

                explanation = explain_variant_selection(
                    product_name=product_name,
                    decision=decision,
                    requested_qty=item.quantity,
                    requested_unit=item.unit
                )
                                
                comparisons[product_name] = {
                    "selected_variant": {
                        "brand": decision["chosen"].brand,
                        "display_quantity": decision["chosen"].weight,
                        "display_unit": decision["chosen"].unit,
                        "vendor": decision["chosen"].vendor,
                        "price": round(decision["total_price"], 2)
                    },
                    "total_price": round(decision["total_price"], 2),
                    "strategy": decision["strategy"],
                    "reasoning": explanation.get("reason") if explanation else decision["reason"],
                    "confidence": explanation.get("confidence", 0.9)
                }


        
        compare_step.status = "completed"
        compare_step.result = f"Compared {len(comparisons)} products"
        
        # Store comparisons in state
        state.decisions_made.append({
            "type": "price_comparison",
            "timestamp": datetime.utcnow().isoformat(),
            "comparisons": comparisons
        })
        
        save_memory(
            state.session_id,
            "decision",
            json.dumps({"type": "price_comparison", "products_compared": len(comparisons)})
        )
        
        logger.info("[EXECUTOR-COMPARE] Price comparison complete")
        return state
    
    except Exception as e:
        logger.error(f"[EXECUTOR-COMPARE] Error: {e}")
        return state

def assemble_shopping_cart(state: AgentState) -> AgentState:
    """
    Build final shopping cart ONLY ONCE.
    After that, replanner is the ONLY authority.
    """
    logger.info(f"[EXECUTOR-CART] Building cart for session {state.session_id}")

    cart_step = next(
        (s for s in state.execution_plan.steps if s.action == "build_cart"),
        None
    )

    if not cart_step:
        return state

    # 🔥 CRITICAL FIX: NEVER rebuild cart if it already exists
    if state.current_cart.items:
        logger.info("[EXECUTOR-CART] Cart already exists — skipping rebuild")
        cart_step.status = "completed"
        cart_step.result = "Cart already built, preserved existing cart"
        return state

    cart_step.status = "in_progress"

    price_decision = None
    for decision_set in state.decisions_made:
        if decision_set.get("type") == "price_comparison":
            price_decision = decision_set["comparisons"]
            break

    if not price_decision:
        cart_step.status = "failed"
        cart_step.error = "No price comparison found"
        return state

    for product_name, decision in price_decision.items():
        item = next(
            (i for i in state.user_grocery_list.items if i.item_name == product_name),
            None
        )

        if not item:
            continue

        variant = decision["selected_variant"]
        
        logger.info(f'[Executor-cart] variant : {variant}')

        # cart_item = CartItem(
        #     product_name=product_name,
        #     brand=variant["brand"],
        #     display_quantity=float(variant["display_quantity"]),
        #     display_unit=variant["display_unit"],
        #     vendor=variant["vendor"],
        #     price=float(variant["price"]),
        #     decision_reason=decision["reasoning"],
        #     # price_per_unit=float(variant["price"]) / float(variant["weight"])
        # )
        
        cart_item = CartItem(
            product_name=product_name,
            brand=variant["brand"],
            weight=float(variant["display_quantity"]),
            unit=variant["display_unit"],
            vendor=variant["vendor"],
            price=float(variant["price"]),
            quantity=1,
            price_per_unit=float(variant["price"]) / float(variant["display_quantity"]),
            # 🔥 DISPLAY (DO NOT REMOVE)
            display_quantity=float(variant["display_quantity"]),
            display_unit=variant["display_unit"],
            decision_reason=decision["reasoning"]
        )


        state.current_cart.add_item(cart_item)

    cart_step.status = "completed"
    cart_step.result = f"Cart built with {len(state.current_cart.items)} items"

    save_memory(
        state.session_id,
        "cart_state",
        json.dumps({
            "items": len(state.current_cart.items),
            "total_price": state.current_cart.total_price
        })
    )

    logger.info("[EXECUTOR-CART] Cart build complete")
    return state
