class TaxCalculator:
    def compute_total_with_tax(self, subtotal: float, is_vip: bool) -> float:
        if subtotal < 0:
            return 0.0

        tax_rate = 0.17 if is_vip else 0.10
        total = subtotal + (subtotal * tax_rate)
        return round(total, 2)
