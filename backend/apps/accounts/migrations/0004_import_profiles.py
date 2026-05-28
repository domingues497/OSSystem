from django.db import migrations, models


def _seed(apps, schema_editor):
    ImportProfile = apps.get_model("accounts", "ImportProfile")
    ImportProfile.objects.get_or_create(
        code="viewprogramacao",
        defaults={
            "name": "Programação (viewprogramacao)",
            "description": "Mapeamento de colunas para o painel Safra 26/27.",
            "source_type": "db_view",
            "source_identifier": "capalti.viewprogramacao",
            "mapping": {},
            "forward_fill": ["vendedor", "cod_empresa", "nome_associado", "cod_imovel", "nome_imovel"],
            "extra_include": [],
            "is_active": True,
        },
    )


def _unseed(apps, schema_editor):
    ImportProfile = apps.get_model("accounts", "ImportProfile")
    try:
        ImportProfile.objects.filter(code="viewprogramacao").delete()
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_navigation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.CharField(blank=True, default="", max_length=255)),
                ("source_type", models.CharField(default="db_view", max_length=32)),
                ("source_identifier", models.CharField(blank=True, default="", max_length=255)),
                ("mapping", models.JSONField(blank=True, default=dict)),
                ("forward_fill", models.JSONField(blank=True, default=list)),
                ("extra_include", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "accounts_import_profile"},
        ),
        migrations.RunPython(_seed, _unseed),
    ]

