from django.conf import settings
from django.db import models
from cryptography.fernet import Fernet, InvalidToken
import base64
import hashlib


def _fernet():
    key_raw = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(key_raw)
    return Fernet(key)


class ADConfiguration(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    host = models.CharField(max_length=255, blank=True, default="")
    port = models.PositiveIntegerField(default=389)
    use_ssl = models.BooleanField(default=False)

    base_dn = models.CharField(max_length=512, blank=True, default="")
    bind_dn = models.CharField(max_length=512, blank=True, default="")
    bind_password_encrypted = models.TextField(blank=True, default="")

    require_group_dn = models.CharField(max_length=512, blank=True, default="")
    deny_group_dn = models.CharField(max_length=512, blank=True, default="")
    require_group_dns = models.JSONField(blank=True, default=list)
    deny_group_dns = models.JSONField(blank=True, default=list)
    staff_group_dns = models.JSONField(blank=True, default=list)
    superuser_group_dns = models.JSONField(blank=True, default=list)

    group_search_dn = models.CharField(max_length=512, blank=True, default="")
    group_object_class = models.CharField(max_length=64, blank=True, default="group")
    group_name_attr = models.CharField(max_length=64, blank=True, default="cn")
    mirror_groups = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_ad_configuration"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def set_bind_password(self, raw_password):
        if raw_password is None:
            return
        raw_password = str(raw_password)
        if raw_password == "":
            self.bind_password_encrypted = ""
            return
        self.bind_password_encrypted = _fernet().encrypt(raw_password.encode("utf-8")).decode("utf-8")

    def get_bind_password(self):
        if not self.bind_password_encrypted:
            return ""
        try:
            return _fernet().decrypt(self.bind_password_encrypted.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return ""
