import logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

class DynamicLDAPBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        cfg = _get_config()
        if not cfg:
            return super().authenticate(request, username=username, password=password, **kwargs)

        if not username or not password:
            return None

        try:
            from ldap3 import Server, Connection, NONE, SUBTREE, BASE
            from ldap3.utils.conv import escape_filter_chars
        except Exception:
            return super().authenticate(request, username=username, password=password, **kwargs)

        host = str(cfg.get("host") or "").strip()
        port = int(cfg.get("port") or 389)
        use_ssl = bool(cfg.get("use_ssl"))
        base_dn = str(cfg.get("base_dn") or "").strip()
        bind_dn = str(cfg.get("bind_dn") or "").strip()
        bind_password = str(cfg.get("bind_password") or "")
        group_search_dn = str(cfg.get("group_search_dn") or "").strip() or base_dn

        if not host or not base_dn or not bind_dn or not bind_password:
            logger.warning("AD auth skipped: missing config fields (host/base_dn/bind_dn/bind_password).")
            return super().authenticate(request, username=username, password=password, **kwargs)

        raw_username = str(username).strip()
        account_name = raw_username
        if "\\" in account_name:
            account_name = account_name.split("\\")[-1]
        if "@" in account_name:
            account_name = account_name.split("@")[0]
        account_name = str(account_name).strip()
        if not account_name:
            return None

        is_superadmin = account_name.lower() in set(getattr(settings, "SUPERADMIN_USERNAMES", []) or [])

        server = Server(host, port=port, use_ssl=use_ssl, get_info=NONE, connect_timeout=10)
        svc_conn = None
        user_conn = None
        try:
            svc_conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True, receive_timeout=10, auto_referrals=False)

            escaped_account = escape_filter_chars(account_name)
            escaped_raw = escape_filter_chars(raw_username)
            user_filter = (
                "(|"
                f"(sAMAccountName={escaped_account})"
                f"(userPrincipalName={escaped_raw})"
                f"(mail={escaped_raw})"
                ")"
            )
            svc_conn.search(
                search_base=base_dn,
                search_filter=user_filter,
                search_scope=SUBTREE,
                attributes=["distinguishedName", "givenName", "sn", "mail"],
                size_limit=2,
            )
            if not svc_conn.entries:
                logger.info(
                    "AD auth: user not found in base_dn. username=%s account=%s base_dn=%s",
                    raw_username,
                    account_name,
                    base_dn,
                )
                return None

            entry = svc_conn.entries[0]
            user_dn = ""
            try:
                user_dn = str(entry.entry_dn or "")
            except Exception:
                user_dn = ""
            if not user_dn:
                logger.info("AD auth: empty DN for user. username=%s base_dn=%s", raw_username, base_dn)
                return None

            try:
                user_conn = Connection(server, user=user_dn, password=str(password), auto_bind=True, receive_timeout=10, auto_referrals=False)
            except Exception as e:
                logger.info("AD auth: user bind failed. username=%s user_dn=%s err=%s", raw_username, user_dn, str(e))
                return None

            require_dns = cfg.get("require_group_dns") or ([str(cfg.get("require_group_dn") or "").strip()] if str(cfg.get("require_group_dn") or "").strip() else [])
            deny_dns = cfg.get("deny_group_dns") or ([str(cfg.get("deny_group_dn") or "").strip()] if str(cfg.get("deny_group_dn") or "").strip() else [])
            staff_dns = cfg.get("staff_group_dns") or []
            super_dns = cfg.get("superuser_group_dns") or []

            def _is_member_of(group_dn: str) -> bool:
                gdn = str(group_dn or "").strip()
                if not gdn:
                    return False
                group_object_class = str(cfg.get("group_object_class") or "group").strip() or "group"
                search_filter = (
                    "(&"
                    f"(objectClass={escape_filter_chars(group_object_class)})"
                    f"(distinguishedName={escape_filter_chars(gdn)})"
                    f"(member:1.2.840.113556.1.4.1941:={escape_filter_chars(user_dn)})"
                    ")"
                )
                try:
                    svc_conn.search(
                        search_base=group_search_dn,
                        search_filter=search_filter,
                        search_scope=SUBTREE,
                        attributes=["distinguishedName"],
                        size_limit=1,
                    )
                    return bool(svc_conn.entries)
                except Exception as e:
                    logger.info(
                        "AD auth: group membership check failed. username=%s user_dn=%s group_dn=%s err=%s",
                        account_name,
                        user_dn,
                        gdn,
                        str(e),
                    )
                    return False

            if not is_superadmin:
                if any(_is_member_of(d) for d in (deny_dns or [])):
                    logger.info("AD auth: denied by group. username=%s user_dn=%s", account_name, user_dn)
                    return None
                if require_dns and not any(_is_member_of(r) for r in (require_dns or [])):
                    logger.info("AD auth: not in required group. username=%s user_dn=%s", account_name, user_dn)
                    return None

            is_staff = bool(is_superadmin) or any(_is_member_of(d) for d in (staff_dns or []))
            is_superuser = bool(is_superadmin) or any(_is_member_of(d) for d in (super_dns or []))

            first_name = ""
            last_name = ""
            email = ""
            try:
                first_name = str(getattr(entry, "givenName").value or "")
            except Exception:
                first_name = ""
            try:
                last_name = str(getattr(entry, "sn").value or "")
            except Exception:
                last_name = ""
            try:
                email = str(getattr(entry, "mail").value or "")
            except Exception:
                email = ""

            UserModel = get_user_model()
            user_obj, _ = UserModel.objects.get_or_create(username=account_name)
            user_obj.first_name = first_name
            user_obj.last_name = last_name
            user_obj.email = email
            user_obj.is_active = True
            user_obj.is_staff = bool(is_staff or is_superuser)
            user_obj.is_superuser = bool(is_superuser)
            user_obj.set_unusable_password()
            user_obj.save()
            return user_obj
        except Exception as e:
            logger.exception("AD auth: unexpected error for username=%s. err=%s", str(username), str(e))
            return None
        finally:
            try:
                if user_conn is not None:
                    user_conn.unbind()
            except Exception:
                pass
            try:
                if svc_conn is not None:
                    svc_conn.unbind()
            except Exception:
                pass


def _get_config():
    cache_key = "accounts:ad_config:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from .models import ADConfiguration
    except Exception:
        cache.set(cache_key, None, timeout=30)
        return None

    cfg = ADConfiguration.get_solo()
    if not cfg.host or not cfg.base_dn:
        cache.set(cache_key, None, timeout=30)
        return None

    data = {
        "host": cfg.host,
        "port": int(cfg.port or 389),
        "use_ssl": bool(cfg.use_ssl),
        "base_dn": cfg.base_dn,
        "bind_dn": cfg.bind_dn,
        "bind_password": cfg.get_bind_password(),
        "require_group_dn": cfg.require_group_dn,
        "deny_group_dn": cfg.deny_group_dn,
        "require_group_dns": cfg.require_group_dns or [],
        "deny_group_dns": cfg.deny_group_dns or [],
        "staff_group_dns": cfg.staff_group_dns or [],
        "superuser_group_dns": cfg.superuser_group_dns or [],
        "group_search_dn": cfg.group_search_dn,
        "group_object_class": cfg.group_object_class,
        "mirror_groups": bool(cfg.mirror_groups),
    }
    cache.set(cache_key, data, timeout=30)
    return data
