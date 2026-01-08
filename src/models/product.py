"""
Product and variant models for the grocery shopping agent.
"""

from pydantic import BaseModel, validator
from typing import Optional


class ProductVariant(BaseModel):
    """Single product variant from a vendor."""
    vendor: str
    product_name: str
    brand: str
    weight: float
    unit: str
    price: float
    category: str
    stock_status: str = "in_stock"
    expiry_days: int = 365

    @validator("price", "weight")
    def check_positive(cls, v):
        if v <= 0:
            raise ValueError("Must be positive")
        return v

    class Config:
        arbitrary_types_allowed = True


class PriceComparison(BaseModel):
    """Price per unit comparison for a product."""
    variant: ProductVariant
    price_per_unit: float  # normalized price per kg/L/piece
    value_score: float  # higher is better (price/quality)
    justification: str

    @validator("price_per_unit", "value_score")
    def check_positive(cls, v):
        if v < 0:
            raise ValueError("Must be non-negative")
        return v

    class Config:
        arbitrary_types_allowed = True
