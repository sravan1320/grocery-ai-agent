"""
Planning agent - generates execution plans based on state.
"""

import uuid
import logging
from models.state import AgentState
from models.plan import ExecutionPlan, PlanningStep

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def create_execution_plan(state: AgentState) -> AgentState:
    """
    Generate execution plan based on current state.
    Decides what actions are needed next.
    """
    logger.info(f"[PLANNER] Generating plan for session {state.session_id}")
    
    steps = []
    # Only add parse step if not parsed yet
    if not state.user_grocery_list:
        steps.append(
            PlanningStep(
                step_id=1,
                action="parse_list",
                description="Parse user's grocery list",
                status="pending"
            )
        )
    else:
        # Build plan to fetch all product variants from all vendors
        step_id = 1
        for item in state.user_grocery_list.items:
            steps.append(
                PlanningStep(
                    step_id=step_id,
                    action="fetch_variants",
                    parameters={"product_name": item.item_name},
                    description=f"Fetch variants for {item.item_name}",
                    status="pending"
                )
            )
            step_id += 1
        
        # Add comparison step
        steps.append(
            PlanningStep(
                step_id=step_id,
                action="compare_prices",
                description="Normalize units and compare prices",
                status="pending"
            )
        )
        step_id += 1
        
        # Add LLM reasoning step
        steps.append(
            PlanningStep(
                step_id=step_id,
                action="llm_reasoning",
                description="Use LLM to reason about best options",
                status="pending"
            )
        )
        step_id += 1
        
        # Add validation step
        steps.append(
            PlanningStep(
                step_id=step_id,
                action="validate_decisions",
                description="Validate LLM decisions with deterministic checks",
                status="pending"
            )
        )
        step_id += 1
        
        # Add cart building step
        steps.append(
            PlanningStep(
                step_id=step_id,
                action="build_cart",
                description="Build final shopping cart",
                status="pending"
            )
        )
        step_id += 1
        
        # Add confirmation step
        steps.append(
            PlanningStep(
                step_id=step_id,
                action="ask_confirmation",
                description="Ask user for confirmation before checkout",
                status="pending"
            )
        )
    
    plan = ExecutionPlan(
        plan_id=str(uuid.uuid4()),
        session_id=state.session_id,
        steps=steps,
        goal="Build optimized grocery shopping cart"
    )
    
    state.execution_plan = plan
    logger.info(f"[PLANNER] Plan created with {len(steps)} steps")
    
    return state
