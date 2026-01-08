"""
API request/response models.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from .product import ProductVariant


class VendorAPIResponse(BaseModel):
    """Response from vendor API (FastAPI endpoint)."""
    product_name: str
    variants: List[ProductVariant]
    search_executed_at: datetime = Field(default_factory=datetime.utcnow)
    api_vendor: str
    status: str = "success"
    error_message: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class APIError(BaseModel):
    """Structured API error response."""
    error_code: str
    error_message: str
    vendor: str
    retry_possible: bool
    retry_after_seconds: int = 5

    class Config:
        arbitrary_types_allowed = True
