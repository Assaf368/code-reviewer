import datetime
from typing import Dict, Tuple

class SecureTokenBucket:
    """Token bucket rate limiter with precise microsecond delta calculation.

    Contract:
    - Capacity and refill rate must be strictly positive.
    - consume deducts requested tokens if available, respecting elapsed time refilling.
    """
    def __init__(self, capacity: int, refill_rate_per_second: float):
        if capacity <= 0:
            raise ValueError("Capacity must be positive.")
        if refill_rate_per_second <= 0:
            raise ValueError("Refill rate must be positive.")
            
        self.capacity: float = float(capacity)
        self.refill_rate: float = refill_rate_per_second
        self._buckets: Dict[str, Tuple[float, datetime.datetime]] = {}

    def _calculate_tokens(self, key: str, now: datetime.datetime) -> float:
        if key not in self._buckets:
            return self.capacity
            
        tokens, last_update = self._buckets[key]
        delta = (now - last_update).total_seconds()
        
        if delta > 0:
            tokens = min(self.capacity, tokens + delta * self.refill_rate)
            
        return tokens

    def consume(self, key: str, tokens_to_consume: int = 1) -> bool:
        if tokens_to_consume <= 0:
            return True
            
        now = datetime.datetime.utcnow()
        current_tokens = self._calculate_tokens(key, now)
        
        if current_tokens < tokens_to_consume:
            self._buckets[key] = (current_tokens, now)
            return False
            
        new_balance = current_tokens - tokens_to_consume
        self._buckets[key] = (new_balance, now)
        return True
