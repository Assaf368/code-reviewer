import datetime
from typing import Dict, List, Any

class ShoppingCart:
    """Manages items, discounts, and final checkout calculations for a user session.

    Contract:
    - add_item adds an item with a positive price and quantity.
    - apply_discount sets a valid percentage discount (0 to 100) on the cart.
    - checkout calculates the final charged amount by applying the percentage discount
      to the subtotal, and then adding a fixed 10% tax on the discounted subtotal.
    """
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.items: List[Dict[str, Any]] = []
        self.discount_percentage: float = 0.0
        self.is_checked_out: bool = False

    def add_item(self, name: str, price: float, quantity: int) -> bool:
        if price <= 0 or quantity <= 0 or self.is_checked_out:
            return False
        self.items.append({"name": name, "price": price, "quantity": quantity})
        return True

    def apply_discount(self, percentage: float) -> bool:
        if not (0 <= percentage <= 100) or self.is_checked_out:
            return False
        self.discount_percentage = percentage
        return True

    def checkout(self) -> float:
        if self.is_checked_out or not self.items:
            return 0.0
        
        subtotal = sum(item["price"] * item["quantity"] for item in self.items)
        
        discounted_subtotal = subtotal * (1 - self.discount_percentage / 100.0)
        
        tax = subtotal * 0.10 
        
        final_amount = discounted_subtotal + tax
        self.is_checked_out = True
        return round(final_amount, 2)
