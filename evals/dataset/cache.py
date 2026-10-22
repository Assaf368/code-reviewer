import datetime
from typing import Dict, Any, Optional, Tuple

class MemoizedDataCache:
    """A TTL-based in-memory cache for complex data payloads.

    Contract:
    - set stores a key-value pair with an expiration time derived from ttl_seconds.
    - get retrieves the cached value if it exists and hasn't expired.
    - get returns the value exactly as it was when set was called.
    """
    def __init__(self, default_ttl_seconds: int = 60):
        self.default_ttl = default_ttl_seconds
        self._store: Dict[str, Tuple[Any, datetime.datetime]] = {}

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl)
        self._store[key] = (value, expiry)

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        
        value, expiry = self._store[key]
        if datetime.datetime.utcnow() > expiry:
            del self._store[key]
            return None
            
        return value

    def clear_expired(self) -> int:
        now = datetime.datetime.utcnow()
        expired_keys = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired_keys:
            del self._store[k]
        return len(expired_keys)
