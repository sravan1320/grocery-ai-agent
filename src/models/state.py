"""
Agent state and reasoning models.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Literal
from datetime import datetime
from .product import ProductVariant
from .cart import Cart
from .grocery_list import ParsedGroceryList
from .plan import ExecutionPlan


class LLMReasoningInput(BaseModel):
    """Input for LLM reasoning (comparison, decisions, etc.)."""
    task: str
    context: Dict
    constraints: Optional[Dict] = None
    previous_decisions: Optional[List[Dict]] = None

    class Config:
        arbitrary_types_allowed = True


class LLMReasoningOutput(BaseModel):
    """Output from LLM reasoning with validation."""
    decision: str
    justification: str
    confidence: float  # 0-1
    metadata: Dict = Field(default_factory=dict)

    @validator("confidence")
    def check_confidence(cls, v):
        if not 0 <= v <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        return v

    class Config:
        arbitrary_types_allowed = True


class AgentState(BaseModel):
    """Current state of the agent during execution."""
    session_id: str
    current_step: int
    execution_plan: ExecutionPlan
    current_cart: Cart
    user_grocery_list: ParsedGroceryList
    all_product_variants: Dict[str, List[ProductVariant]] = Field(default_factory=dict)
    decisions_made: List[Dict] = Field(default_factory=list)
    messages_to_user: List[str] = Field(default_factory=list)
    awaiting_user_input: bool = False
    user_input: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    processing_feedback: bool = False

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True

class AgentMemoryEntry(BaseModel):
    """Entry stored in agent's persistent memory (SQLite)."""
    session_id: str
    memory_type: Literal["decision", "reasoning", "preference", "api_call", "error", "cart_state"]
    content: str
    metadata: Optional[Dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True