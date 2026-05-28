from django.db import migrations


def _seed(apps, schema_editor):
    InternalField = apps.get_model("accounts", "InternalField")
    InternalField.objects.update_or_create(
        key="safra",
        defaults={
            "label": "Safra",
            "required": False,
            "aliases": ["safra", "safra_2627", "safra_26_27", "safra 26/27", "safra 2627"],
            "order": 15,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_internal_fields"),
    ]

    operations = [
        migrations.RunPython(_seed, migrations.RunPython.noop),
    ]

