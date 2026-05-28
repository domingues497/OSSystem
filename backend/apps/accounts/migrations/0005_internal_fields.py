from django.db import migrations, models


def _seed(apps, schema_editor):
    InternalField = apps.get_model("accounts", "InternalField")
    defaults = [
        {
            "key": "vendedor",
            "label": "Agrônomo",
            "required": True,
            "aliases": ["agronomo", "agrônomo", "vendedor", "rotulos_de_linha", "nome_vendedor", "seller"],
            "order": 10,
            "is_active": True,
        },
        {
            "key": "cod_empresa",
            "label": "Cód. Empresa",
            "required": False,
            "aliases": ["cod_empresa", "codigo_empresa", "empresa"],
            "order": 20,
            "is_active": True,
        },
        {
            "key": "nome_associado",
            "label": "Associado",
            "required": True,
            "aliases": ["nome_associado", "associado", "produtor", "cliente"],
            "order": 30,
            "is_active": True,
        },
        {
            "key": "cod_imovel",
            "label": "Cód. Imóvel",
            "required": False,
            "aliases": ["cod_imovel", "codigo_imovel"],
            "order": 40,
            "is_active": True,
        },
        {
            "key": "nome_imovel",
            "label": "Imóvel / Fazenda",
            "required": True,
            "aliases": ["nome_imovel", "imovel", "fazenda", "propriedade"],
            "order": 50,
            "is_active": True,
        },
        {
            "key": "nome_gleba",
            "label": "Gleba / Talhão",
            "required": True,
            "aliases": ["nome_gleba", "gleba", "talhao", "talhão"],
            "order": 60,
            "is_active": True,
        },
        {
            "key": "area_cultivavel",
            "label": "Área Cultivável",
            "required": True,
            "aliases": ["area_cultivavel", "area cultivavel", "hectares", "ha", "area", "soma de area_cultivavel"],
            "order": 70,
            "is_active": True,
        },
        {
            "key": "area_planejada",
            "label": "Área Planejada",
            "required": False,
            "aliases": ["area_planejada", "area planejada", "soma de area planejada"],
            "order": 80,
            "is_active": True,
        },
    ]
    for f in defaults:
        key = f.pop("key")
        InternalField.objects.update_or_create(key=key, defaults=f)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_import_profiles"),
    ]

    operations = [
        migrations.CreateModel(
            name="InternalField",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=80, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("required", models.BooleanField(default=False)),
                ("aliases", models.JSONField(blank=True, default=list)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "accounts_internal_field",
                "ordering": ["order", "label", "key"],
            },
        ),
        migrations.RunPython(_seed, migrations.RunPython.noop),
    ]
