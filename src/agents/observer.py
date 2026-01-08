"""
Observer agents - validate decisions and handle user interactions.
"""

import json
import logging
from datetime import datetime

from models.state import AgentState
from core.llm_engine import (
    validate_llm_decision    
)
from core.db import get_db_connection
from utils.memory_utils import save_memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# def save_memory(session_id: str, memory_type: str, content: str, metadata: dict = None):
#     """Save agent memory to persistent storage."""
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor()
        
#         cursor.execute("""
#             INSERT INTO agent_memory (session_id, memory_type, content, metadata)
#             VALUES (?, ?, ?, ?)
#         """, (session_id, memory_type, content, json.dumps(metadata or {})))
        
#         conn.commit()
#         conn.close()
#         logger.info(f"Memory saved: {memory_type}")
#     except Exception as e:
#         logger.error(f"Failed to save memory: {e}")


def apply_llm_reasoning(state: AgentState) -> AgentState:
    """
    Use LLM reasoning to make final vendor/variant selections.
    """
    from src.core import reason_vendor_selection
    
    logger.info(f"[EXECUTOR-REASON] LLM reasoning for session {state.session_id}")
    
    try:
        reason_step = next(
            (s for s in state.execution_plan.steps if s.action == "llm_reasoning"),
            None
        )
        
        if not reason_step or not state.all_product_variants:
            return state
        
        reason_step.status = "in_progress"
        
        reasoning_results = {}
        
        for product_name, variants in state.all_product_variants.items():
            if not variants:
                continue
            
            # Group variants by vendor
            by_vendor = {}
            for v in variants:
                if v.vendor not in by_vendor:
                    by_vendor[v.vendor] = []
                by_vendor[v.vendor].append(v)
            
            # Use LLM to select best vendor
            result = reason_vendor_selection(product_name, by_vendor)
            
            if result and validate_llm_decision(result, "vendor_selection"):
                reasoning_results[product_name] = result
                logger.info(f"[EXECUTOR-REASON] Selected vendor for {product_name}: {result.get('selected_vendor')}")
        
        reason_step.status = "completed"
        reason_step.result = f"LLM reasoning for {len(reasoning_results)} products"
        
        state.decisions_made.append({
            "type": "llm_reasoning",
            "timestamp": datetime.utcnow().isoformat(),
            "reasoning": reasoning_results
        })
        
        save_memory(
            state.session_id,
            "decision",
            json.dumps({"type": "llm_reasoning", "products_reasoned": len(reasoning_results)})
        )
        
        logger.info("[EXECUTOR-REASON] Reasoning complete")
        return state
    
    except Exception as e:
        logger.error(f"[EXECUTOR-REASON] Error: {e}")
        return state


def validate_cart_decisions(state: AgentState) -> AgentState:
    """
    Validate all LLM decisions using deterministic checks.
    Ensures decisions are sound before using them.
    """
    logger.info(f"[OBSERVER-VALIDATE] Validating decisions for session {state.session_id}")
    
    try:
        validate_step = next(
            (s for s in state.execution_plan.steps if s.action == "validate_decisions"),
            None
        )
        
        if not validate_step:
            return state
        
        validate_step.status = "in_progress"
        
        validation_results = {
            "passed": 0,
            "failed": 0,
            "errors": []
        }
        
        # Check each decision
        for decision_set in state.decisions_made:
            if decision_set.get("type") == "llm_reasoning":
                for product, reasoning in decision_set.get("reasoning", {}).items():
                    # Validate vendor is valid
                    vendor = reasoning.get("selected_vendor")
                    if vendor not in ["zepto", "blinkit", "swiggy_instamart", "bigbasket"]:
                        validation_results["failed"] += 1
                        validation_results["errors"].append(f"Invalid vendor for {product}: {vendor}")
                    else:
                        validation_results["passed"] += 1
        
        validate_step.status = "completed"
        validate_step.result = f"Validation: {validation_results['passed']} passed, {validation_results['failed']} failed"
        
        if validation_results["failed"] > 0:
            logger.warning(f"[OBSERVER-VALIDATE] Some validations failed: {validation_results['errors']}")
            state.messages_to_user.append(f"Warning: {validation_results['failed']} validation issues found")
        
        save_memory(
            state.session_id,
            "decision",
            json.dumps({"type": "validation", "results": validation_results})
        )
        
        logger.info("[OBSERVER-VALIDATE] Validation complete")
        return state
    
    except Exception as e:
        logger.error(f"[OBSERVER-VALIDATE] Error: {e}")
        return state


def request_user_confirmation(state: AgentState) -> AgentState:
    """
    Ask user for confirmation before checkout.
    Sets awaiting_user_input flag for UI to handle.
    """
    logger.info(f"[OBSERVER-ASK] Asking confirmation for session {state.session_id}")
    
    try:
        confirm_step = next(
            (s for s in state.execution_plan.steps if s.action == "ask_confirmation"),
            None
        )
        logger.info(f'[OBSERVER-ASK] confirm_step -> {confirm_step}')
        if not confirm_step:
            return state
        
        confirm_step.status = "in_progress"
        
        # Format cart summary
        cart_summary = f"""
Your Shopping Cart (₹{state.current_cart.total_price:.2f}):
{len(state.current_cart.items)} items selected

"""
        logger.info(f'[OBSERVER-ASK] cart_summary -> {cart_summary}')
        for item in state.current_cart.items:
            cart_summary += f"• {item.brand} {item.display_unit} from {item.vendor.upper()} - ₹{item.price}\n"
        
        state.messages_to_user.append(cart_summary)
        state.messages_to_user.append("\nOptions:\n1. Confirm and checkout\n2. Modify item\n3. Remove item\n4. Recompare specific product")
        
        state.awaiting_user_input = True
        logger.info(f'[OBSERVER-ASK] cart_summary -> {cart_summary}')
        confirm_step.status = "pending"  # Waiting for user input
        
        logger.info("[OBSERVER-ASK] Confirmation requested")
        
        return state
    
    except Exception as e:
        logger.error(f"[OBSERVER-ASK] Error: {e}")
        return state


def persist_session_memory(state: AgentState) -> AgentState:
    """
    Save final state to persistent memory for session recovery.
    """
    logger.info(f"[MEMORY] Saving state for session {state.session_id}")
    
    try:
        save_memory(
            state.session_id,
            "cart_state",
            json.dumps({
                "total_items": len(state.current_cart.items),
                "total_price": state.current_cart.total_price,
                "items": [
                    {
                        "product": item.product_name,
                        "brand": item.brand,
                        "vendor": item.vendor,
                        "price": item.price
                    }
                    for item in state.current_cart.items
                ]
            })
        )
        
        logger.info("[MEMORY] State saved successfully")
        return state
    
    except Exception as e:
        logger.error(f"[MEMORY] Error saving state: {e}")
        return state
