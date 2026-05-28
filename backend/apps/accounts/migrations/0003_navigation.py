from django.db import migrations, models
import django.db.models.deletion


def _seed(apps, schema_editor):
    Feature = apps.get_model("accounts", "Feature")
    Menu = apps.get_model("accounts", "Menu")
    MenuItem = apps.get_model("accounts", "MenuItem")

    f, _ = Feature.objects.get_or_create(
        code="commissions",
        defaults={"name": "Comissões", "description": "Gestão de comissões e notas fiscais.", "is_active": True},
    )
    f_admin, _ = Feature.objects.get_or_create(
        code="admin",
        defaults={"name": "Admin", "description": "Administração do sistema.", "is_active": True},
    )
    f_ad, _ = Feature.objects.get_or_create(
        code="ad_config",
        defaults={"name": "Config AD", "description": "Configuração e testes LDAP/AD.", "is_active": True},
    )
    m, _ = Menu.objects.get_or_create(
        title="Módulos",
        defaults={"order": 0, "is_active": True},
    )
    MenuItem.objects.get_or_create(
        menu=m,
        title="Comissões",
        defaults={"path": "/dashboard/", "order": 0, "is_active": True, "feature_id": f.id},
    )
    m_sys, _ = Menu.objects.get_or_create(
        title="Sistema",
        defaults={"order": 100, "is_active": True},
    )
    MenuItem.objects.get_or_create(
        menu=m_sys,
        title="Admin",
        defaults={"path": "/admin/", "order": 0, "is_active": True, "feature_id": f_admin.id},
    )
    MenuItem.objects.get_or_create(
        menu=m_sys,
        title="Config AD",
        defaults={"path": "/ad-config/", "order": 10, "is_active": True, "feature_id": f_ad.id},
    )


def _unseed(apps, schema_editor):
    Feature = apps.get_model("accounts", "Feature")
    Menu = apps.get_model("accounts", "Menu")
    MenuItem = apps.get_model("accounts", "MenuItem")

    try:
        MenuItem.objects.filter(title="Comissões", path="/dashboard/").delete()
    except Exception:
        pass
    try:
        MenuItem.objects.filter(title="Admin", path="/admin/").delete()
    except Exception:
        pass
    try:
        MenuItem.objects.filter(title="Config AD", path="/ad-config/").delete()
    except Exception:
        pass
    try:
        Menu.objects.filter(title="Módulos").delete()
    except Exception:
        pass
    try:
        Menu.objects.filter(title="Sistema").delete()
    except Exception:
        pass
    try:
        Feature.objects.filter(code__in=["commissions", "admin", "ad_config"]).delete()
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_ad_multigroups"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Feature",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.CharField(blank=True, default="", max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("groups", models.ManyToManyField(blank=True, related_name="features_allowed", to="auth.group")),
                ("users", models.ManyToManyField(blank=True, related_name="features_allowed", to="auth.user")),
            ],
            options={"db_table": "accounts_feature"},
        ),
        migrations.CreateModel(
            name="Menu",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("groups", models.ManyToManyField(blank=True, related_name="menus_allowed", to="auth.group")),
                ("users", models.ManyToManyField(blank=True, related_name="menus_allowed", to="auth.user")),
            ],
            options={"db_table": "accounts_menu", "ordering": ["order", "title"]},
        ),
        migrations.CreateModel(
            name="MenuItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("path", models.CharField(max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("feature", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="menu_items", to="accounts.feature")),
                ("groups", models.ManyToManyField(blank=True, related_name="menu_items_allowed", to="auth.group")),
                ("menu", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="accounts.menu")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="accounts.menuitem")),
                ("users", models.ManyToManyField(blank=True, related_name="menu_items_allowed", to="auth.user")),
            ],
            options={"db_table": "accounts_menu_item", "ordering": ["order", "title"]},
        ),
        migrations.RunPython(_seed, _unseed),
    ]
