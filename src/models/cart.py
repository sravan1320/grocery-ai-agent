"""
Shopping cart models.
"""

from pydantic import BaseModel, Field, validator
from typing import List
from datetime import datetime


class CartItem(BaseModel):
    """Item selected for shopping cart."""
    product_name: str
    brand: str
    # weight: float
    # unit: str
    vendor: str
    price: float
    # quantity: float = Field(default=1.0, gt=0)
    decision_reason: str
    # price_per_unit: float
    selected_at: datetime = Field(default_factory=datetime.utcnow)
    display_quantity: float
    display_unit: str

    class Config:
        arbitrary_types_allowed = True


class Cart(BaseModel):
    """Shopping cart with multiple items."""
    session_id: str
    items: List[CartItem] = Field(default_factory=list)
    total_price: float = 0.0
    total_items: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def add_item(self, item: CartItem):
        for existing in self.items:
            if existing.product_name == item.product_name:
                existing.brand = item.brand
                existing.vendor = item.vendor
                # existing.weight = item.weight
                existing.display_unit = item.display_unit
                existing.price = item.price              # TOTAL price
                existing.display_quantity = item.display_quantity
                existing.decision_reason = item.decision_reason
                # existing.price_per_unit = item.price_per_unit
                existing.selected_at = datetime.utcnow()
                break
        else:
            self.items.append(item)

        # ✅ CORRECT TOTAL
        self.total_price = sum(i.price for i in self.items)
        self.total_items = len(self.items)
        self.last_updated = datetime.utcnow()


    def remove_item(self, product_name: str, brand: str):
        self.items = [
            i for i in self.items
            if not (i.product_name == product_name and i.brand == brand)
        ]
        self.total_price = sum(i.price for i in self.items)
        self.total_items = sum(i.display_quantity for i in self.items)
        self.last_updated = datetime.utcnow()


    def recalculate_total(self):
        self.total_price = sum(i.price for i in self.items)
        self.total_items = sum(i.display_quantity for i in self.items)
        self.last_updated = datetime.utcnow()


    class Config:
        arbitrary_types_allowed = True
