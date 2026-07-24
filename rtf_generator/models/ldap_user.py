"""
models/ldap_user.py

Modelo de usuário autenticado via Active Directory (LDAP).

Este modelo é independente de Flask e Django e representa o usuário
retornado pelo LDAPService após uma autenticação bem-sucedida.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LDAPUser:
    """
    Representa um usuário autenticado no Active Directory.
    """

    username: str
    distinguished_name: str

    display_name: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    department: str = ""
    title: str = ""
    employee_id: str = ""
    company: str = ""
    telephone: str = ""
    mobile: str = ""

    groups: list[str] = field(default_factory=list)

    is_staff: bool = False
    is_superuser: bool = False
    is_active: bool = True

    raw_attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        if self.display_name:
            return self.display_name.strip()

        return f"{self.first_name} {self.last_name}".strip()

    @property
    def initials(self) -> str:
        parts = self.full_name.split()

        if not parts:
            return ""

        if len(parts) == 1:
            return parts[0][:2].upper()

        return f"{parts[0][0]}{parts[-1][0]}".upper()

    @property
    def login(self) -> str:
        return self.username

    def has_group(self, group_dn: str) -> bool:
        return any(g.lower() == group_dn.lower() for g in self.groups)

    def has_any_group(self, groups: list[str]) -> bool:
        return any(self.has_group(group) for group in groups)

    def add_group(self, group_dn: str) -> None:
        if not self.has_group(group_dn):
            self.groups.append(group_dn)

    def remove_group(self, group_dn: str) -> None:
        self.groups = [
            g for g in self.groups
            if g.lower() != group_dn.lower()
        ]

    def get_attribute(self, name: str, default: Any = None) -> Any:
        return self.raw_attributes.get(name, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "distinguished_name": self.distinguished_name,
            "display_name": self.display_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "email": self.email,
            "department": self.department,
            "title": self.title,
            "employee_id": self.employee_id,
            "company": self.company,
            "telephone": self.telephone,
            "mobile": self.mobile,
            "groups": self.groups,
            "is_staff": self.is_staff,
            "is_superuser": self.is_superuser,
            "is_active": self.is_active,
            "raw_attributes": self.raw_attributes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LDAPUser":
        return cls(
            username=data.get("username", ""),
            distinguished_name=data.get("distinguished_name", ""),
            display_name=data.get("display_name", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            email=data.get("email", ""),
            department=data.get("department", ""),
            title=data.get("title", ""),
            employee_id=data.get("employee_id", ""),
            company=data.get("company", ""),
            telephone=data.get("telephone", ""),
            mobile=data.get("mobile", ""),
            groups=list(data.get("groups") or []),
            is_staff=bool(data.get("is_staff", False)),
            is_superuser=bool(data.get("is_superuser", False)),
            is_active=bool(data.get("is_active", True)),
            raw_attributes=dict(data.get("raw_attributes") or {}),
        )

    def __str__(self) -> str:
        return (
            f"{self.full_name or self.username} "
            f"<{self.email}>"
        )

    def __repr__(self) -> str:
        return (
            f"LDAPUser(username={self.username!r}, "
            f"display_name={self.display_name!r})"
        )
