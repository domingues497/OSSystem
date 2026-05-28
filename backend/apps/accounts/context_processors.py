from .models import Menu


def navigation(request):
    user = getattr(request, "user", None)
    menus_out = []

    try:
        menus = (
            Menu.objects.all()
            .prefetch_related("items", "items__feature", "items__children", "items__children__feature")
            .order_by("order", "title")
        )
    except Exception:
        return {"menus": []}

    for menu in menus:
        if not menu.is_allowed(user):
            continue

        root_items = [i for i in menu.items.all() if i.parent_id is None and i.is_allowed(user)]
        root_items.sort(key=lambda x: (x.order, (x.title or "").lower()))

        items_out = []
        for item in root_items:
            children = [c for c in item.children.all() if c.is_allowed(user)]
            children.sort(key=lambda x: (x.order, (x.title or "").lower()))
            items_out.append({
                "title": item.title,
                "path": item.path,
                "children": [{"title": c.title, "path": c.path} for c in children],
            })

        if items_out:
            menus_out.append({"title": menu.title, "items": items_out})

    if user and getattr(user, "is_authenticated", False) and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)):
        menus_out.append({
            "title": "Sistema",
            "items": [
                {"title": "Controle de Acesso", "path": "/access-control/", "children": []},
                {"title": "Mapeamento de Colunas", "path": "/import-mapping/", "children": []},
                {"title": "Config AD", "path": "/ad-config/", "children": []},
                {"title": "Admin", "path": "/admin/", "children": []},
            ],
        })

    return {"menus": menus_out}
