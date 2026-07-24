"""
repositories/ad_configuration_repository.py

Repository responsável por carregar a configuração do Active Directory
armazenada na tabela capalti.accounts_ad_configuration.
"""

from __future__ import annotations

import json
import logging

from database.erp_connection import get_erp_connection
from exceptions.ldap_exceptions import (
    ADConfigurationNotFound,
    ConfigurationLoadError,
)
from models.ad_configuration import ADConfiguration
from services.crypto_service import CryptoService

logger = logging.getLogger(__name__)


class ADConfigurationRepository:
    """Repository de configuração do Active Directory."""

    def __init__(self, secret_key: str):
        self._crypto = CryptoService(secret_key)

    @staticmethod
    def _to_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [value]
        return list(value)

    def get_configuration(self) -> ADConfiguration:
        sql = """
            SELECT
                id,
                host,
                port,
                use_ssl,
                base_dn,
                bind_dn,
                bind_password_encrypted,
                require_group_dns,
                deny_group_dns,
                staff_group_dns,
                superuser_group_dns,
                group_search_dn,
                group_object_class,
                group_name_attr,
                mirror_groups
            FROM capalti.accounts_ad_configuration
            WHERE id = 1
        """

        conn = None
        cur = None

        try:
            conn = get_erp_connection()
            cur = conn.cursor()
            cur.execute(sql)

            row = cur.fetchone()

            if row is None:
                raise ADConfigurationNotFound(
                    "Configuração do Active Directory não encontrada."
                )

            encrypted_password = row[6] or ""

            config = ADConfiguration(
                id=row[0],
                host=row[1],
                port=row[2],
                use_ssl=row[3],
                base_dn=row[4],
                bind_dn=row[5],
                bind_password=self._crypto.decrypt_if_needed(
                    encrypted_password
                ),
                require_group_dns=self._to_list(row[7]),
                deny_group_dns=self._to_list(row[8]),
                staff_group_dns=self._to_list(row[9]),
                superuser_group_dns=self._to_list(row[10]),
                group_search_dn=row[11] or row[4],
                group_object_class=row[12] or "group",
                group_name_attr=row[13] or "cn",
                mirror_groups=bool(row[14]),
            )

            config.validate()

            logger.info(
                "Configuração LDAP carregada com sucesso (%s).",
                config.host,
            )

            return config

        except Exception as exc:
            logger.exception("Erro ao carregar configuração LDAP.")
            raise ConfigurationLoadError(str(exc)) from exc

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
