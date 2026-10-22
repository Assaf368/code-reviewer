import datetime
from typing import Any, Dict

class ResourceLockManager:
    """Manages exclusive locks on named resources with automatic lease timeouts.

    Contract:
    - acquire locks a resource for a specific owner if it's unlocked or its lease expired.
    - release unlocks the resource only if the requesting owner holds the active lock.
    """
    def __init__(self, default_lease_seconds: int = 30):
        self.default_lease = default_lease_seconds
        self.locks: Dict[str, Dict[str, Any]] = {}

    def acquire(self, resource_id: str, owner_id: str) -> bool:
        now = datetime.datetime.utcnow()
        
        if resource_id in self.locks:
            lock_info = self.locks[resource_id]
            if now < lock_info["expires_at"]:
                if lock_info["owner"] != owner_id:
                    return False
                lock_info["expires_at"] = now + datetime.timedelta(seconds=self.default_lease)
                return True

        self.locks[resource_id] = {
            "owner": owner_id,
            "expires_at": now + datetime.timedelta(seconds=self.default_lease)
        }
        return True

    def release(self, resource_id: str, owner_id: str) -> bool:
        if resource_id not in self.locks:
            return False
            
        lock_info = self.locks[resource_id]
        
        if lock_info["owner"] != owner_id:
            return False
            
        del self.locks[resource_id]
        return True
