from typing import List, Dict, Any

class PricingCalculator:
    """Calculates the final price for a set of items.
    
    This class handles standard cart evaluations and applies the given 
    modifier to the calculation.
    """
    
    def compute_final_price(self, line_items: List[Dict[str, Any]], modifier_value: float) -> float:
        """Computes the final price of the order.
        
        Args:
            line_items: The items included in the calculation.
            modifier_value: The value applied to adjust the total sum.
            
        Returns:
            The final calculated price as a rounded float.
        """
        base_sum = sum(item["unit_price"] * item.get("qty", 1) for item in line_items)
        
        adjusted = base_sum - modifier_value
        
        return round(max(0.0, adjusted), 2)
