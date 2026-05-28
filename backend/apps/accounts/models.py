from django.conf import settings
from django.db import models
from django.contrib.auth.models import Group, User
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


class Feature(models.Model):
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)
    users = models.ManyToManyField(User, blank=True, related_name="features_allowed")
    groups = models.ManyToManyField(Group, blank=True, related_name="features_allowed")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_feature"

    def __str__(self):
        return self.name

    def is_allowed(self, user):
        if not self.is_active:
            return False
        if user and getattr(user, "is_superuser", False):
            return True
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if not self.users.exists() and not self.groups.exists():
            return False
        if self.users.filter(pk=user.pk).exists():
            return True
        return self.groups.filter(pk__in=user.groups.values_list("pk", flat=True)).exists()


class Menu(models.Model):
    title = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    users = models.ManyToManyField(User, blank=True, related_name="menus_allowed")
    groups = models.ManyToManyField(Group, blank=True, related_name="menus_allowed")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_menu"
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

    def is_allowed(self, user):
        if not self.is_active:
            return False
        if user and getattr(user, "is_superuser", False):
            return True
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if not self.users.exists() and not self.groups.exists():
            return True
        if self.users.filter(pk=user.pk).exists():
            return True
        return self.groups.filter(pk__in=user.groups.values_list("pk", flat=True)).exists()


class MenuItem(models.Model):
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    title = models.CharField(max_length=120)
    path = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    feature = models.ForeignKey(Feature, null=True, blank=True, on_delete=models.SET_NULL, related_name="menu_items")
    users = models.ManyToManyField(User, blank=True, related_name="menu_items_allowed")
    groups = models.ManyToManyField(Group, blank=True, related_name="menu_items_allowed")

    class Meta:
        db_table = "accounts_menu_item"
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

    def is_allowed(self, user):
        if not self.is_active:
            return False
        if user and getattr(user, "is_superuser", False):
            return True
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if self.feature and not self.feature.is_allowed(user):
            return False
        if not self.users.exists() and not self.groups.exists():
            return False
        if self.users.filter(pk=user.pk).exists():
            return True
        if self.groups.filter(pk__in=user.groups.values_list("pk", flat=True)).exists():
            return True
        return False


class ImportProfile(models.Model):
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True, default="")
    source_type = models.CharField(max_length=32, default="db_view")
    source_identifier = models.CharField(max_length=255, blank=True, default="")
    mapping = models.JSONField(default=dict, blank=True)
    forward_fill = models.JSONField(default=list, blank=True)
    extra_include = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_import_profile"

    def __str__(self):
        return self.name


class InternalField(models.Model):
    key = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    required = models.BooleanField(default=False)
    aliases = models.JSONField(default=list, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_internal_field"
        ordering = ["order", "label", "key"]

    def __str__(self):
        return self.label
