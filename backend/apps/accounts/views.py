from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .serializers import RegisterSerializer, UserSerializer
from .models import ADConfiguration, Menu, MenuItem, Feature, ImportProfile, InternalField
from ldap3 import Server, Connection, NONE, ALL, SUBTREE
from django.core.cache import cache
from django.db import connections
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.text import slugify
import re

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


@never_cache
@login_required
def home_page(request):
    return render(request, "home.html")


@never_cache
@login_required
def planejamento_safra_2627_page(request):
    allowed = bool(
        request.user
        and (
            request.user.is_superuser
            or request.user.is_staff
            or request.user.menu_items_allowed.filter(path="/planejamento/safra-2627/").exists()
        )
    )
    if not allowed:
        return render(request, "home.html")
    return render(request, "planejamento e safra/Safra 2627 — Painel de Áreas.jsx")


@never_cache
@login_required
@require_GET
def viewprogramacao_api(request):
    allowed = bool(
        request.user
        and (
            request.user.is_superuser
            or request.user.is_staff
            or request.user.menu_items_allowed.filter(path="/planejamento/safra-2627/").exists()
        )
    )
    if not allowed:
        return JsonResponse({"error": "Acesso não liberado."}, status=403)

    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("select * from capalti.viewprogramacao")
            cols = [str(c[0] or "").lower() for c in cursor.description]
            rows = cursor.fetchall()
        data = [dict(zip(cols, r)) for r in rows]
        profile = None
        try:
            profile = ImportProfile.objects.filter(code="viewprogramacao", is_active=True).first()
        except Exception:
            profile = None
        internal_fields = []
        try:
            internal_fields = [
                {
                    "key": f.key,
                    "label": f.label,
                    "required": bool(f.required),
                    "aliases": list(f.aliases or []),
                }
                for f in InternalField.objects.filter(is_active=True).order_by("order", "label", "key")
            ]
        except Exception:
            internal_fields = []
        return JsonResponse(
            {
                "columns": cols,
                "rows": data,
                "profile": {
                    "code": getattr(profile, "code", "viewprogramacao"),
                    "mapping": getattr(profile, "mapping", {}) or {},
                    "forward_fill": getattr(profile, "forward_fill", []) or [],
                    "extra_include": getattr(profile, "extra_include", []) or [],
                },
                "internal_fields": internal_fields,
            },
            encoder=DjangoJSONEncoder,
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@never_cache
@login_required
@user_passes_test(lambda u: bool(u and (u.is_staff or u.is_superuser)))
def import_mapping_page(request, code=None):
    internal_fields_base = []
    fallback_fields = [
        {"key": "vendedor", "label": "Agrônomo", "required": True},
        {"key": "safra", "label": "Safra", "required": False},
        {"key": "cod_empresa", "label": "Cód. Empresa", "required": False},
        {"key": "nome_associado", "label": "Associado", "required": True},
        {"key": "cod_imovel", "label": "Cód. Imóvel", "required": False},
        {"key": "nome_imovel", "label": "Imóvel / Fazenda", "required": True},
        {"key": "nome_gleba", "label": "Gleba / Talhão", "required": True},
        {"key": "area_cultivavel", "label": "Área Cultivável", "required": True},
        {"key": "area_planejada", "label": "Área Planejada", "required": False},
    ]
    try:
        internal_fields_base = list(
            InternalField.objects.filter(is_active=True)
            .order_by("order", "label", "key")
            .values("key", "label", "required")
        )
    except Exception:
        internal_fields_base = []
    if not internal_fields_base:
        internal_fields_base = fallback_fields

    profiles = ImportProfile.objects.filter(is_active=True).order_by("name", "code")
    profile = None
    if code:
        profile = profiles.filter(code=code).first()
    if profile is None:
        profile = profiles.first()
    if profile is None:
        profile = None

    def _safe_identifier(ident: str) -> str:
        raw = str(ident or "").strip()
        if not raw:
            return ""
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?", raw):
            return ""
        return raw

    create_error = ""
    if request.method == "POST" and request.POST.get("action") == "create_profile":
        name = str(request.POST.get("new_name") or "").strip()
        code_in = str(request.POST.get("new_code") or "").strip()
        source_type = str(request.POST.get("new_source_type") or "db_view").strip() or "db_view"
        source_identifier = _safe_identifier(request.POST.get("new_source_identifier"))
        description = str(request.POST.get("new_description") or "").strip()

        if not name:
            create_error = "Informe o nome."
        elif source_type != "db_view":
            create_error = "Tipo de origem inválido."
        elif not source_identifier:
            create_error = "Informe um identificador válido (ex.: capalti.viewprogramacao)."
        else:
            code_slug = slugify(code_in or name).replace("-", "_")
            if not code_slug:
                create_error = "Código inválido."
            else:
                try:
                    new_profile = ImportProfile.objects.create(
                        code=code_slug,
                        name=name,
                        description=description,
                        source_type=source_type,
                        source_identifier=source_identifier,
                        mapping={},
                        forward_fill=["vendedor", "cod_empresa", "nome_associado", "cod_imovel", "nome_imovel"],
                        extra_include=[],
                        is_active=True,
                    )
                    return redirect(f"/import-mapping/{new_profile.code}/?created=1")
                except Exception:
                    create_error = "Não foi possível criar. Verifique se o código já existe."

        return render(request, "accounts/import_mapping.html", {
            "profiles": profiles,
            "profile": profile,
            "columns": [],
            "internal_fields": [],
            "saved": False,
            "created": False,
            "create_error": create_error,
        })

    if profile is None:
        return render(request, "accounts/import_mapping.html", {"profiles": profiles, "profile": None, "create_error": create_error})

    columns = []
    if profile.source_type == "db_view":
        ident = _safe_identifier(profile.source_identifier)
        if ident:
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute(f"select * from {ident} limit 0")
                    columns = [str(c[0] or "").lower() for c in cursor.description]
            except Exception:
                columns = []

    if request.method == "POST":
        mapping = {}
        for f in internal_fields_base:
            key = str(f["key"])
            col = str(request.POST.get(f"map_{key}") or "").strip()
            mapping[key] = col

        ff = [str(f["key"]) for f in internal_fields_base if request.POST.get(f"ff_{f['key']}")]
        extra_include = [str(x or "").strip() for x in request.POST.getlist("extra_include") if str(x or "").strip()]

        profile.mapping = mapping
        profile.forward_fill = ff
        profile.extra_include = extra_include
        profile.save(update_fields=["mapping", "forward_fill", "extra_include", "updated_at"])

        return redirect(f"/import-mapping/{profile.code}/?saved=1")

    mapping = profile.mapping or {}
    forward_fill = set(profile.forward_fill or [])
    internal_fields = []
    for f in internal_fields_base:
        key = str(f["key"])
        internal_fields.append({
            "key": key,
            "label": f["label"],
            "required": bool(f["required"]),
            "selected": str(mapping.get(key) or ""),
            "ff": key in forward_fill,
        })

    return render(
        request,
        "accounts/import_mapping.html",
        {
            "profiles": profiles,
            "profile": profile,
            "columns": columns,
            "internal_fields": internal_fields,
            "saved": request.GET.get("saved") == "1",
            "created": request.GET.get("created") == "1",
            "create_error": create_error,
        },
    )


@never_cache
@login_required
@user_passes_test(lambda u: bool(u and (u.is_staff or u.is_superuser)))
def access_control_page(request, user_id=None):
    users = User.objects.filter(is_active=True).order_by("username")
    selected_user = None
    if user_id is not None:
        selected_user = get_object_or_404(users, pk=user_id)
    else:
        selected_user = users.first()

    if not selected_user:
        return render(request, "accounts/access_control.html", {"users": [], "selected_user": None, "menus": []})

    if request.method == "POST":
        selected_ids = request.POST.getlist("menu_items")
        selected_ids = [int(x) for x in selected_ids if str(x).isdigit()]
        items = MenuItem.objects.filter(is_active=True, pk__in=selected_ids).select_related("feature", "menu", "parent")
        selected_user.menu_items_allowed.set(items)

        feature_ids = sorted({i.feature_id for i in items if i.feature_id})
        feature_codes = []
        if feature_ids:
            for feature in Feature.objects.filter(pk__in=feature_ids):
                feature.users.add(selected_user)
                feature_codes.append(feature.code)

        feature_perm_map = {
            "commissions": [
                "commissions.view_consultor",
                "commissions.view_comissao",
                "commissions.view_recebimento",
                "commissions.view_periodocomissao",
                "commissions.view_comissaoconsultorperiodo",
                "commissions.add_comissaoconsultorperiodo",
            ],
        }
        managed_perms = sorted({p for perms in feature_perm_map.values() for p in perms})
        selected_perms = sorted({p for code in feature_codes for p in feature_perm_map.get(code, [])})

        perms_to_add = [p for p in selected_perms if p in managed_perms]
        perms_to_remove = [p for p in managed_perms if p not in selected_perms]

        if perms_to_remove:
            remove_q = Permission.objects.none()
            for full in perms_to_remove:
                app_label, codename = full.split(".", 1)
                remove_q = remove_q | Permission.objects.filter(content_type__app_label=app_label, codename=codename)
            selected_user.user_permissions.remove(*remove_q)

        if perms_to_add:
            add_q = Permission.objects.none()
            for full in perms_to_add:
                app_label, codename = full.split(".", 1)
                add_q = add_q | Permission.objects.filter(content_type__app_label=app_label, codename=codename)
            selected_user.user_permissions.add(*add_q)

        return redirect(f"/access-control/{selected_user.id}/?saved=1")

    direct_item_ids = set(selected_user.menu_items_allowed.values_list("id", flat=True))

    menus = (
        Menu.objects.filter(is_active=True)
        .prefetch_related("items", "items__children", "items__feature", "items__children__feature")
        .order_by("order", "title")
    )

    menus_out = []
    for menu in menus:
        items = [i for i in menu.items.all() if i.parent_id is None and i.is_active]
        items.sort(key=lambda x: (x.order, (x.title or "").lower()))
        items_out = []
        for item in items:
            children = [c for c in item.children.all() if c.is_active]
            children.sort(key=lambda x: (x.order, (x.title or "").lower()))
            items_out.append({
                "id": item.id,
                "title": item.title,
                "path": item.path,
                "feature": item.feature.code if item.feature_id else "",
                "direct": item.id in direct_item_ids,
                "children": [{
                    "id": c.id,
                    "title": c.title,
                    "path": c.path,
                    "feature": c.feature.code if c.feature_id else "",
                    "direct": c.id in direct_item_ids,
                } for c in children],
            })
        if items_out:
            menus_out.append({"id": menu.id, "title": menu.title, "items": items_out})

    return render(request, "accounts/access_control.html", {
        "users": users,
        "selected_user": selected_user,
        "menus": menus_out,
        "saved": request.GET.get("saved") == "1",
    })
