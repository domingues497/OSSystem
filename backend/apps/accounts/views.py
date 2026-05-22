from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from .serializers import RegisterSerializer, UserSerializer
from .models import ADConfiguration
from ldap3 import Server, Connection, NONE, ALL, SUBTREE
from django.core.cache import cache

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class MeView(generics.GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class ADConfigView(APIView):
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        cfg = ADConfiguration.get_solo()
        bind_password_ok = bool(cfg.get_bind_password())
        return Response({
            "host": cfg.host,
            "port": cfg.port,
            "use_ssl": cfg.use_ssl,
            "base_dn": cfg.base_dn,
            "bind_dn": cfg.bind_dn,
            "has_bind_password": bind_password_ok,
            "group_search_dn": cfg.group_search_dn,
            "group_object_class": cfg.group_object_class,
            "group_name_attr": cfg.group_name_attr,
            "mirror_groups": cfg.mirror_groups,
            "require_group_dn": cfg.require_group_dn,
            "deny_group_dn": cfg.deny_group_dn,
            "require_group_dns": cfg.require_group_dns or ([cfg.require_group_dn] if cfg.require_group_dn else []),
            "deny_group_dns": cfg.deny_group_dns or ([cfg.deny_group_dn] if cfg.deny_group_dn else []),
            "staff_group_dns": cfg.staff_group_dns or [],
            "superuser_group_dns": cfg.superuser_group_dns or [],
        })

    def put(self, request):
        payload = request.data or {}
        cfg = ADConfiguration.get_solo()

        cfg.host = str(payload.get("host") or "").strip()
        cfg.port = int(payload.get("port") or 389)
        cfg.use_ssl = bool(payload.get("use_ssl"))
        cfg.base_dn = str(payload.get("base_dn") or "").strip()
        cfg.bind_dn = str(payload.get("bind_dn") or "").strip()
        cfg.group_search_dn = str(payload.get("group_search_dn") or "").strip()
        cfg.group_object_class = str(payload.get("group_object_class") or "group").strip() or "group"
        cfg.group_name_attr = str(payload.get("group_name_attr") or "cn").strip() or "cn"
        cfg.mirror_groups = bool(payload.get("mirror_groups"))

        cfg.require_group_dn = str(payload.get("require_group_dn") or "").strip()
        cfg.deny_group_dn = str(payload.get("deny_group_dn") or "").strip()

        require_dns = payload.get("require_group_dns")
        deny_dns = payload.get("deny_group_dns")
        if require_dns is None:
            require_dns = [cfg.require_group_dn] if cfg.require_group_dn else []
        if deny_dns is None:
            deny_dns = [cfg.deny_group_dn] if cfg.deny_group_dn else []
        if not isinstance(require_dns, list):
            require_dns = [require_dns]
        if not isinstance(deny_dns, list):
            deny_dns = [deny_dns]
        cfg.require_group_dns = [str(d or "").strip() for d in require_dns if str(d or "").strip()]
        cfg.deny_group_dns = [str(d or "").strip() for d in deny_dns if str(d or "").strip()]
        staff_dns = payload.get("staff_group_dns") or []
        super_dns = payload.get("superuser_group_dns") or []
        cfg.staff_group_dns = staff_dns if isinstance(staff_dns, list) else [staff_dns]
        cfg.superuser_group_dns = super_dns if isinstance(super_dns, list) else [super_dns]

        raw_pass = payload.get("bind_password")
        if raw_pass is not None:
            cfg.set_bind_password(raw_pass)
        else:
            if not cfg.get_bind_password():
                return Response({"ok": False, "error": "Informe a senha do Bind DN."}, status=status.HTTP_400_BAD_REQUEST)

        cfg.save()
        cache.delete("accounts:ad_config:v1")
        return Response({"ok": True})


class ADTestConnectionView(APIView):
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        payload = request.data or {}
        host = str(payload.get("host") or "").strip()
        port = int(payload.get("port") or 389)
        use_ssl = bool(payload.get("use_ssl"))
        base_dn = str(payload.get("base_dn") or "").strip()
        bind_dn = str(payload.get("bind_dn") or "").strip()
        bind_password = str(payload.get("bind_password") or "")

        if not host or not base_dn or not bind_dn or not bind_password:
            return Response({"ok": False, "error": "Preencha Host, Base DN, Bind DN e Senha."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            server = Server(host, port=port, use_ssl=use_ssl, get_info=NONE, connect_timeout=10)
            conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True, receive_timeout=10, auto_referrals=False)
            conn.unbind()
            return Response({"ok": True})
        except Exception as e:
            return Response({"ok": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ADGroupsView(APIView):
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        payload = request.data or {}
        host = str(payload.get("host") or "").strip()
        port = int(payload.get("port") or 389)
        use_ssl = bool(payload.get("use_ssl"))
        base_dn = str(payload.get("base_dn") or "").strip()
        bind_dn = str(payload.get("bind_dn") or "").strip()
        bind_password = str(payload.get("bind_password") or "")
        group_search_dn = str(payload.get("group_search_dn") or "").strip() or base_dn
        group_object_class = str(payload.get("group_object_class") or "group").strip() or "group"
        group_name_attr = str(payload.get("group_name_attr") or "cn").strip() or "cn"

        if not host or not base_dn or not bind_dn or not bind_password:
            return Response({"ok": False, "error": "Preencha Host, Base DN, Bind DN e Senha."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            server = Server(host, port=port, use_ssl=use_ssl, get_info=NONE, connect_timeout=10)
            conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True, receive_timeout=10, auto_referrals=False)
            conn.search(
                search_base=group_search_dn,
                search_filter=f"(objectClass={group_object_class})",
                search_scope=SUBTREE,
                attributes=[group_name_attr],
                paged_size=500,
            )
            groups = []
            for entry in conn.entries:
                dn = str(entry.entry_dn or "")
                name = ""
                try:
                    name = str(getattr(entry, group_name_attr).value or "")
                except Exception:
                    name = ""
                if not dn:
                    continue
                groups.append({"dn": dn, "name": name or dn})
            conn.unbind()
            groups.sort(key=lambda g: (g.get("name") or "").lower())
            return Response({"ok": True, "groups": groups})
        except Exception as e:
            return Response({"ok": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@never_cache
@login_required
@user_passes_test(lambda u: bool(u and (u.is_staff or u.is_superuser)))
def ad_config_page(request):
    return render(request, "accounts/ad_config.html")
