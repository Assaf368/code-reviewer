from typing import List, Dict, Any

class DiscountEngine:
    def __init__(self, base_items: List[Dict[str, Any]]):
        self.items = base_items

    def calculate_total(self, percentage_discount: float, flat_discount: float) -> float:
        subtotal = sum(item["price"] * item["qty"] for item in self.items)

        reduced_by_percent = subtotal * (1 - percentage_discount / 100.0)
        final_price = reduced_by_percent - flat_discount

        return max(0.0, round(final_price, 2))
