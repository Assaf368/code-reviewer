import logging
import datetime
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ConfigurationRegistry:
    """Process-wide settings shared by all services."""

    _settings: Dict[str, Any] = {
        "MAX_CART_ITEMS": 50,
        "DEFAULT_CURRENCY": "USD",
        "TAX_RATE": 0.17,
        "ENABLE_DISCOUNTS": True
    }

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        return cls._settings.get(key, default)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        cls._settings[key] = value


class UserService:
    def __init__(self):
        self._users: Dict[str, Dict[str, Any]] = {}

    def register_user(self, username: str, email: str, is_vip: bool = False) -> str:
        """Register a user and return its id.

        The id is derived from the username and is stable within one process.
        Registering an existing username replaces that user.
        """
        user_id = f"usr_{abs(hash(username))}"
        self._users[user_id] = {
            "username": username,
            "email": email,
            "is_vip": is_vip,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        logging.info(f"User registered successfully: {username} ({user_id})")
        return user_id

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._users.get(user_id)


class InventoryService:
    def __init__(self):
        self._inventory: Dict[str, Dict[str, Any]] = {
            "item_01": {"name": "Laptop", "price": 1200.0, "stock": 10},
            "item_02": {"name": "Mouse", "price": 25.0, "stock": 50},
            "item_03": {"name": "Keyboard", "price": 75.0, "stock": 30},
            "item_04": {"name": "Monitor", "price": 300.0, "stock": 15}
        }

    def check_stock(self, item_id: str, quantity: int) -> bool:
        """Return True if item_id exists and at least quantity units are in stock."""
        item = self._inventory.get(item_id)
        if not item:
            return False
        return item["stock"] >= quantity

    def deduct_stock(self, item_id: str, quantity: int) -> None:
        """Remove quantity units of item_id from stock. Does nothing if stock is short."""
        if self.check_stock(item_id, quantity):
            self._inventory[item_id]["stock"] -= quantity
            logging.info(f"Stock deducted for {item_id}: -{quantity}")

    def get_item_price(self, item_id: str) -> float:
        """Return the unit price of item_id, or 0.0 if it does not exist."""
        item = self._inventory.get(item_id)
        return item["price"] if item else 0.0


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, user_id: str) -> str:
        """Open an active session for user_id and return its id."""
        session_id = f"sess_{user_id}_{len(self._sessions) + 1}"
        self._sessions[session_id] = {
            "user_id": user_id,
            "active": True,
            "attempts": 0,
            "opened_at": datetime.datetime.utcnow().isoformat()
        }
        logging.info(f"Session created: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(session_id)

    def invalidate_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["active"] = False
            logging.info(f"Session invalidated: {session_id}")


class PaymentProcessor:
    def __init__(self, session_mgr: SessionManager, inventory_svc: InventoryService):
        self.session_mgr = session_mgr
        self.inventory_svc = inventory_svc
        self.transaction_history: List[Dict[str, Any]] = []

    def validate_cart(self, items: List[Dict[str, Any]]) -> bool:
        """Return True if the whole cart can be fulfilled.

        items is a list of {"item_id": str, "quantity": int}. The same item_id
        may appear in several entries. The cart is valid if it is not empty,
        has at most MAX_CART_ITEMS entries, every quantity is positive, and
        stock covers the total quantity requested for each item.
        """
        if not items:
            return False
        max_items = ConfigurationRegistry.get("MAX_CART_ITEMS", 50)
        if len(items) > max_items:
            return False

        for entry in items:
            item_id = entry.get("item_id")
            qty = entry.get("quantity", 0)
            if qty <= 0 or not self.inventory_svc.check_stock(item_id, qty):
                return False
        return True

    def calculate_total(self, items: List[Dict[str, Any]], discount_code: Optional[str] = None) -> float:
        """Return the amount to charge for items.

        discount_code is applied only when the ENABLE_DISCOUNTS setting is on:
        "SUMMER10" takes 10% off and "VIP20" takes 20% off. Tax at TAX_RATE is
        added after the discount. Amounts are floats rounded to 2 decimals.
        """
        subtotal = 0.0
        for entry in items:
            price = self.inventory_svc.get_item_price(entry["item_id"])
            subtotal += price * entry["quantity"]

        if discount_code == "SUMMER10":
            subtotal *= 0.90
        elif discount_code == "VIP20":
            subtotal *= 0.80

        tax_rate = ConfigurationRegistry.get("TAX_RATE", 0.0)
        final_amount = subtotal * (1 + tax_rate)
        return round(final_amount, 2)

    def process_payment(self, session_id: str, items: List[Dict[str, Any]], discount_code: Optional[str] = None) -> bool:
        """Charge for items in an active session and record the transaction.

        On success, stock is deducted for every entry and a record is appended
        to transaction_history. Its charged_amount is the amount actually
        charged, as returned by calculate_total. Returns False, and changes
        nothing, if the session is not active or the cart is not valid.
        """
        session = self.session_mgr.get_session(session_id)

        if not session or not session.get("active"):
            logging.error("Invalid or inactive session detected during payment.")
            return False

        if not self.validate_cart(items):
            logging.error("Cart validation or stock check failed.")
            return False

        total_amount = self.calculate_total(items, discount_code)

        raw_subtotal = 0.0
        for entry in items:
            item_price = self.inventory_svc.get_item_price(entry["item_id"])
            raw_subtotal += item_price * entry["quantity"]
            self.inventory_svc.deduct_stock(entry["item_id"], entry["quantity"])

        transaction_record = {
            "session_id": session_id,
            "user_id": session["user_id"],
            "charged_amount": raw_subtotal,
            "currency": ConfigurationRegistry.get("DEFAULT_CURRENCY"),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "status": "SUCCESS"
        }

        self.transaction_history.append(transaction_record)
        logging.info(f"Payment processed successfully for user {session['user_id']}")
        return True


class AuditService:
    def __init__(self, payment_processor: PaymentProcessor):
        self.processor = payment_processor

    def verify_user_totals(self, user_id: str) -> float:
        """Return the sum charged to user_id over all successful transactions."""
        total = 0.0
        for tx in self.processor.transaction_history:
            if tx["user_id"] == user_id and tx["status"] == "SUCCESS":
                total += tx["charged_amount"]
        return total
