"""
exceptions/ldap_exceptions.py

Exceções customizadas para o módulo LDAP.
"""


class LDAPException(Exception):
    """Exceção base para o módulo LDAP."""


class ADConfigurationNotFound(LDAPException):
    """Configuração do Active Directory não encontrada."""


class InvalidBindPassword(LDAPException):
    """Senha do Bind DN inválida ou não pôde ser descriptografada."""


class LDAPConnectionError(LDAPException):
    """Falha ao conectar ao servidor LDAP."""


class LDAPAuthenticationError(LDAPException):
    """Falha na autenticação do usuário no LDAP."""


class LDAPAuthorizationError(LDAPException):
    """Usuário autenticado, porém sem autorização."""


class LDAPUserNotFound(LDAPException):
    """Usuário não encontrado no Active Directory."""


class LDAPGroupNotFound(LDAPException):
    """Grupo LDAP não encontrado."""


class LDAPInvalidConfiguration(LDAPException):
    """Configuração LDAP inválida."""


class LDAPTimeoutError(LDAPException):
    """Tempo limite excedido durante operação LDAP."""


class LDAPOperationError(LDAPException):
    """Erro durante operação LDAP."""


class RepositoryError(Exception):
    """Erro genérico de repositório."""


class DatabaseConnectionError(RepositoryError):
    """Falha ao conectar ao banco de dados."""


class ConfigurationLoadError(RepositoryError):
    """Erro ao carregar configuração do Active Directory."""


__all__ = [
    "LDAPException",
    "ADConfigurationNotFound",
    "InvalidBindPassword",
    "LDAPConnectionError",
    "LDAPAuthenticationError",
    "LDAPAuthorizationError",
    "LDAPUserNotFound",
    "LDAPGroupNotFound",
    "LDAPInvalidConfiguration",
    "LDAPTimeoutError",
    "LDAPOperationError",
    "RepositoryError",
    "DatabaseConnectionError",
    "ConfigurationLoadError",
]
