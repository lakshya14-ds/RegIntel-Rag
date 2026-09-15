"""
Authority Filter Abstraction for Multi-Regulator Retrieval (Phases 70–72).

Provides a unified filter interface to restrict retrieval across:
- All authorities (unconstrained / None)
- Single authority (e.g. ['IRDAI'] or 'IRDAI')
- Multiple authorities (e.g. ['RBI', 'SEBI'])
"""

from typing import List, Optional, Union, Dict, Any


class AuthorityFilter:
    """
    Shared authority filter abstraction for multi-regulator retrieval and compliance querying.
    """

    def __init__(self, authorities: Optional[Union[str, List[str]]] = None):
        if authorities is None:
            self.authorities: List[str] = []
        elif isinstance(authorities, str):
            clean = authorities.strip()
            if clean and clean.upper() not in {"ALL", "ALL REGULATORS"}:
                self.authorities = [clean]
            else:
                self.authorities = []
        else:
            self.authorities = [
                a.strip()
                for a in authorities
                if a and a.strip().upper() not in {"ALL", "ALL REGULATORS"}
            ]

    @property
    def is_unconstrained(self) -> bool:
        """Returns True if all regulatory authorities are permitted."""
        return len(self.authorities) == 0

    def to_mongo_query(self, field_name: str = "authority") -> Dict[str, Any]:
        """
        Generates MongoDB query constraint for filtering.
        Supports both single equality and $in arrays.
        """
        if self.is_unconstrained:
            return {}
        if len(self.authorities) == 1:
            return {field_name: self.authorities[0]}
        return {field_name: {"$in": self.authorities}}

    def matches(self, item: Any) -> bool:
        """
        Evaluates whether a chunk, document, or dictionary matches this authority filter.
        """
        if self.is_unconstrained:
            return True

        val = None
        if isinstance(item, dict):
            val = item.get("authority") or item.get("source")
        else:
            val = getattr(item, "authority", None) or getattr(item, "source", None)

        if not val:
            return False
        return str(val).upper() in {a.upper() for a in self.authorities}

    def __repr__(self) -> str:
        if self.is_unconstrained:
            return "AuthorityFilter(ALL)"
        return f"AuthorityFilter({self.authorities})"
