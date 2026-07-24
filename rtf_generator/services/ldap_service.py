"""
services/ldap_service.py

Cliente LDAP reutilizável para autenticação em Active Directory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPException

from exceptions.ldap_exceptions import (
    LDAPAuthenticationError,
    LDAPConnectionError,
    LDAPUserNotFound,
)
from repositories.ad_configuration_repository import ADConfigurationRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LDAPUser:
    username: str
    distinguished_name: str
    display_name: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    department: str = ""
    title: str = ""
    groups: list[str] = field(default_factory=list)
    raw_attributes: dict = field(default_factory=dict)


class LDAPService:

    def __init__(self, secret_key: str):
        self._config = ADConfigurationRepository(secret_key).get_configuration()
        self._server = Server(
            self._config.host,
            port=self._config.port,
            use_ssl=self._config.use_ssl,
            get_info=ALL,
        )
        self._service_connection: Connection | None = None

    def connect(self) -> None:
        try:
            self._service_connection = Connection(
                self._server,
                user=self._config.bind_dn,
                password=self._config.bind_password,
                auto_bind=True,
            )
            logger.info("Conectado ao LDAP.")
        except LDAPException as exc:
            raise LDAPConnectionError(str(exc)) from exc

    def disconnect(self):
        if self._service_connection:
            self._service_connection.unbind()
            self._service_connection = None

    def health_check(self) -> bool:
        try:
            self.connect()
            return True
        except Exception:
            return False
        finally:
            self.disconnect()

    def search_user(self, username: str) -> LDAPUser:
        if not self._service_connection:
            self.connect()

        search_filter = (
            f"(|(sAMAccountName={username})"
            f"(userPrincipalName={username}))"
        )

        attrs = [
            "distinguishedName",
            "givenName",
            "sn",
            "displayName",
            "mail",
            "department",
            "title",
            "memberOf",
            "sAMAccountName",
        ]

        self._service_connection.search(
            search_base=self._config.base_dn,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attrs,
        )

        if not self._service_connection.entries:
            raise LDAPUserNotFound(username)

        entry = self._service_connection.entries[0]

        data = entry.entry_attributes_as_dict

        return LDAPUser(
            username=data.get("sAMAccountName", [username])[0]
            if isinstance(data.get("sAMAccountName"), list)
            else data.get("sAMAccountName", username),
            distinguished_name=str(entry.entry_dn),
            first_name=data.get("givenName", ""),
            last_name=data.get("sn", ""),
            display_name=data.get("displayName", ""),
            email=data.get("mail", ""),
            department=data.get("department", ""),
            title=data.get("title", ""),
            groups=list(data.get("memberOf") or []),
            raw_attributes=data,
        )

    def authenticate(self, username: str, password: str) -> LDAPUser:
        user = self.search_user(username)

        try:
            conn = Connection(
                self._server,
                user=user.distinguished_name,
                password=password,
                auto_bind=True,
            )
            conn.unbind()
        except LDAPException as exc:
            raise LDAPAuthenticationError(
                "Usuário ou senha inválidos."
            ) from exc

        return user

    @staticmethod
    def is_member(user: LDAPUser, group_dn: str) -> bool:
        return any(g.lower() == group_dn.lower() for g in user.groups)

    def get_groups(self, username: str) -> list[str]:
        return self.search_user(username).groups
