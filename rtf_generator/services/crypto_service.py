"""
services/crypto_service.py

Serviço responsável pela criptografia/descriptografia do Bind DN.
Compatível com a implementação utilizada no Django.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class CryptoService:
    """
    Serviço de criptografia baseado em Fernet.

    A chave é derivada da SECRET_KEY utilizando:
      - SHA256
      - Base64 URL Safe

    Compatível com a implementação existente no Django.
    """

    def __init__(self, secret_key: str):
        if not secret_key:
            raise ValueError("SECRET_KEY não pode ser vazia.")
        self._secret_key = secret_key
        self._fernet = Fernet(self.generate_key(secret_key))

    @staticmethod
    def generate_key(secret_key: str) -> bytes:
        digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    @staticmethod
    def validate_secret_key(secret_key: str) -> bool:
        return isinstance(secret_key, str) and len(secret_key.strip()) >= 16

    @staticmethod
    def is_encrypted(value: str) -> bool:
        return isinstance(value, str) and value.startswith("gAAAA")

    def encrypt(self, plain_text: str) -> str:
        if plain_text is None:
            raise ValueError("Texto não pode ser None.")

        if plain_text == "":
            return ""

        logger.debug("Criptografando valor.")
        token = self._fernet.encrypt(plain_text.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, encrypted_text: str) -> str:
        if encrypted_text is None:
            raise ValueError("Valor criptografado não pode ser None.")

        if encrypted_text == "":
            return ""

        try:
            logger.debug("Descriptografando valor.")
            return self._fernet.decrypt(
                encrypted_text.encode("utf-8")
            ).decode("utf-8")
        except InvalidToken as exc:
            logger.error("Falha ao descriptografar o conteúdo.")
            raise ValueError(
                "Não foi possível descriptografar o valor informado."
            ) from exc

    def encrypt_if_needed(self, value: str) -> str:
        if self.is_encrypted(value):
            return value
        return self.encrypt(value)

    def decrypt_if_needed(self, value: str) -> str:
        if not self.is_encrypted(value):
            return value
        return self.decrypt(value)

    def test(self) -> bool:
        sample = "ldap_test"
        encrypted = self.encrypt(sample)
        decrypted = self.decrypt(encrypted)
        return sample == decrypted
