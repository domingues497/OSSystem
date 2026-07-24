"""
models/ad_configuration.py

Modelo de configuração do Active Directory utilizado pelo módulo LDAP.
Compatível com Flask (sem dependências do Django).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ADConfiguration:
    """
    Representa a configuração do Active Directory carregada do PostgreSQL.
    """

    id: int = 1

    host: str = ""
    port: int = 389
    use_ssl: bool = False

    base_dn: str = ""
    bind_dn: str = ""
    bind_password: str = ""

    require_group_dns: list[str] = field(default_factory=list)
    deny_group_dns: list[str] = field(default_factory=list)

    staff_group_dns: list[str] = field(default_factory=list)
    superuser_group_dns: list[str] = field(default_factory=list)

    group_search_dn: str = ""
    group_object_class: str = "group"
    group_name_attr: str = "cn"

    mirror_groups: bool = False

    @property
    def ldap_uri(self) -> str:
        protocol = "ldaps" if self.use_ssl else "ldap"
        return f"{protocol}://{self.host}:{self.port}"

    def validate(self) -> None:
        if not self.host:
            raise ValueError("Host do Active Directory não informado.")

        if self.port <= 0:
            raise ValueError("Porta inválida.")

        if not self.base_dn:
            raise ValueError("Base DN não informado.")

        if not self.bind_dn:
            raise ValueError("Bind DN não informado.")

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "ADConfiguration":
        return cls(
            id=record.get("id", 1),
            host=record.get("host", ""),
            port=record.get("port", 389),
            use_ssl=record.get("use_ssl", False),
            base_dn=record.get("base_dn", ""),
            bind_dn=record.get("bind_dn", ""),
            bind_password=record.get("bind_password", ""),
            require_group_dns=list(record.get("require_group_dns") or []),
            deny_group_dns=list(record.get("deny_group_dns") or []),
            staff_group_dns=list(record.get("staff_group_dns") or []),
            superuser_group_dns=list(record.get("superuser_group_dns") or []),
            group_search_dn=record.get("group_search_dn", ""),
            group_object_class=record.get("group_object_class", "group"),
            group_name_attr=record.get("group_name_attr", "cn"),
            mirror_groups=record.get("mirror_groups", False),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "host": self.host,
            "port": self.port,
            "use_ssl": self.use_ssl,
            "base_dn": self.base_dn,
            "bind_dn": self.bind_dn,
            "bind_password": self.bind_password,
            "require_group_dns": self.require_group_dns,
            "deny_group_dns": self.deny_group_dns,
            "staff_group_dns": self.staff_group_dns,
            "superuser_group_dns": self.superuser_group_dns,
            "group_search_dn": self.group_search_dn,
            "group_object_class": self.group_object_class,
            "group_name_attr": self.group_name_attr,
            "mirror_groups": self.mirror_groups,
        }

    def __str__(self) -> str:
        return (
            f"ADConfiguration(host={self.host}, port={self.port}, "
            f"use_ssl={self.use_ssl}, base_dn={self.base_dn})"
        )
