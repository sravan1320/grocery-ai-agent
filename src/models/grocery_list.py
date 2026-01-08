"""
Grocery list related models.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime


class ParsedGroceryItem(BaseModel):
    """Parsed item from user's grocery list."""
    item_name: str
    quantity: float = Field(default=1.0, gt=0)
    unit: str
    notes: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class ParsedGroceryList(BaseModel):
    """Structured grocery list after LLM parsing."""
    items: List[ParsedGroceryItem]
    original_input: str
    parsed_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
