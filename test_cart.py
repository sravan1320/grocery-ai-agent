from src.models.cart import CartItem

def cart_item_creation():
    item = CartItem(
        product_name="Apple",
        brand="FreshFarms",
        weight=1.0,
        unit="kg",
        vendor="Local Market",
        price=3.5,
        quantity=0.5,
        decision_reason="Best price",
        price_per_unit=3.5
    )
    # assert item.product_name == "Apple"
    # assert item.quantity == 0.5
    # assert item.price == 3.5
    
    print(f"CartItem created successfully: {item}")

cart_item_creation()