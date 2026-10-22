import datetime
from typing import Dict, Any, Optional

class UserSessionManager:
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    def create_or_update_session(self, user_id: str, metadata: dict) -> str:
        session_token = f"tok_{user_id}_{int(datetime.datetime.utcnow().timestamp())}"
        self.active_sessions[user_id] = {
            "token": session_token,
            "metadata": metadata,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        return session_token

    def get_session_metadata(self, user_id: str) -> Optional[dict]:
        return self.active_sessions.get(user_id)
