"""
Super Agent Orchestrator - coordinates all agents using LangGraph.
Implements dynamic control flow: Planner → Executor → Observer → Replanner loop.
"""

import uuid
import logging
from typing import Optional

from langgraph.graph import StateGraph, END

from models.state import AgentState
from models.grocery_list import ParsedGroceryList
from models.plan import ExecutionPlan
from models.cart import Cart
from .planner import create_execution_plan
from .executor import (
    parse_grocery_list,
    fetch_product_variants,
    compare_and_rank_products,
    assemble_shopping_cart,
)
from .observer import (
    apply_llm_reasoning,
    validate_cart_decisions,
    request_user_confirmation,
    persist_session_memory,
)
from .replanner import process_user_feedback, confirm_checkout

# ❗ DO NOT CHANGE LOG FORMAT (as requested)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def router(state: AgentState) -> str:
    """
    Router to determine next action dynamically.
    """

    if state.awaiting_user_input and not state.user_input:
        return END

    if state.awaiting_user_input and state.user_input and not state.processing_feedback:
        logger.info(f"[ROUTER] User feedback received: {state.user_input}")

        # 🔒 Lock feedback so it runs exactly once
        state.processing_feedback = True

        if state.user_input.lower() in ["confirm", "yes", "checkout", "proceed"]:
            return "confirm_checkout"

        # 🔑 ALL other cases → replanner
        return "process_feedback"

    # 🔒 AFTER FEEDBACK IS PROCESSED — HARD STOP
    if state.processing_feedback:
        logger.info("[ROUTER] Feedback processed — returning to UI")
        state.processing_feedback = False
        state.awaiting_user_input = True
        state.user_input = None

        # ❌ DO NOT continue execution plan
        return END

    # ================================
    # ⏳ WAITING STATE
    # ================================
    if state.awaiting_user_input and not state.user_input:
        logger.info("[ROUTER] Awaiting user input")
        return END

    # ================================
    # 🚦 NORMAL EXECUTION FLOW
    # ================================
    if not state.execution_plan:
        logger.info("[ROUTER] No execution plan present")
        return END

    logger.info(
        f"state.execution_plan.steps: "
        f"{[s.action + ':' + s.status for s in state.execution_plan.steps]}"
    )

    for step in state.execution_plan.steps:
        if step.status == "pending":
            logger.info(f"[ROUTER] Next step: {step.action}")

            if step.action == "parse_list":
                return "parse_input"
            elif step.action == "fetch_variants":
                return "fetch_variants"
            elif step.action == "compare_prices":
                return "compare_prices"
            elif step.action == "llm_reasoning":
                return "llm_reasoning"
            elif step.action == "validate_decisions":
                return "validate_decisions"
            elif step.action == "build_cart":
                return "build_cart"
            elif step.action == "ask_confirmation":
                return "ask_confirmation"

    logger.info("[ROUTER] All steps completed")
    return "save_memory"


def build_super_agent_graph():
    """
    Build LangGraph for autonomous super-agent.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("plan", create_execution_plan)
    workflow.add_node("parse_input", parse_grocery_list)
    workflow.add_node("fetch_variants", fetch_product_variants)
    workflow.add_node("compare_prices", compare_and_rank_products)
    workflow.add_node("llm_reasoning", apply_llm_reasoning)
    workflow.add_node("validate_decisions", validate_cart_decisions)
    workflow.add_node("build_cart", assemble_shopping_cart)
    workflow.add_node("ask_confirmation", request_user_confirmation)
    workflow.add_node("process_feedback", process_user_feedback)
    workflow.add_node("confirm_checkout", confirm_checkout)
    workflow.add_node("save_memory", persist_session_memory)

    workflow.set_entry_point("plan")

    workflow.add_conditional_edges("plan", router)
    workflow.add_conditional_edges("parse_input", router)
    workflow.add_conditional_edges("fetch_variants", router)
    workflow.add_conditional_edges("compare_prices", router)
    workflow.add_conditional_edges("llm_reasoning", router)
    workflow.add_conditional_edges("validate_decisions", router)
    workflow.add_conditional_edges("build_cart", router)
    workflow.add_conditional_edges("ask_confirmation", router)
    workflow.add_conditional_edges("process_feedback", router)

    workflow.add_edge("confirm_checkout", "save_memory")
    workflow.add_edge("save_memory", END)

    return workflow.compile()


def execute_agent(
    user_grocery_list: ParsedGroceryList,
    session_id: Optional[str] = None,
    existing_state: Optional[AgentState] = None,
) -> AgentState:
    """
    Execute the autonomous super-agent.
    """

    if not session_id:
        session_id = str(uuid.uuid4())

    logger.info(f"[AGENT] Starting execution for session {session_id}")
    logger.info(
        f"[AGENT] User wants: "
        f"{[f'{i.quantity}{i.unit} {i.item_name}' for i in user_grocery_list.items]}"
    )

    if existing_state:
        initial_state = existing_state
    else:
        initial_state = AgentState(
            session_id=session_id,
            current_step=0,
            execution_plan=ExecutionPlan(
                plan_id="",
                session_id=session_id,
                steps=[],
                goal="",
            ),
            current_cart=Cart(session_id=session_id),
            user_grocery_list=user_grocery_list,
            all_product_variants={},
            decisions_made=[],
            messages_to_user=[],
        )

    graph = build_super_agent_graph()
    result = graph.invoke(initial_state)

    # LangGraph returns dict
    final_state = AgentState(**result)

    logger.info(
        f"[AGENT] Execution complete. Cart: "
        f"{len(final_state.current_cart.items)} items, "
        f"₹{final_state.current_cart.total_price:.2f}"
    )

    return final_state
