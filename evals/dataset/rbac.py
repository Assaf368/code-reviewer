from typing import Dict, List, Set

class RBACEngine:
    """Role-Based Access Control engine with hierarchical role inheritance."""

    def __init__(self):
        self.roles: Dict[str, Set[str]] = {}
        self.inheritance: Dict[str, Set[str]] = {}

    def define_role(self, role_name: str, permissions: List[str]) -> None:
        self.roles[role_name] = set(permissions)
        if role_name not in self.inheritance:
            self.inheritance[role_name] = set()

    def inherit_role(self, child_role: str, parent_role: str) -> None:
        if child_role not in self.inheritance:
            self.inheritance[child_role] = set()
        self.inheritance[child_role].add(parent_role)

    def has_permission(self, role_name: str, permission: str) -> bool:
        if role_name not in self.roles:
            return False
            
        if permission in self.roles[role_name]:
            return True
            
        parents = self.inheritance.get(role_name, set())
        for parent in parents:
            if parent in self.roles and permission in self.roles[parent]:
                return True
                
        return False
