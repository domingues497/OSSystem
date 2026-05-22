from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ADConfiguration",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("host", models.CharField(blank=True, default="", max_length=255)),
                ("port", models.PositiveIntegerField(default=389)),
                ("use_ssl", models.BooleanField(default=False)),
                ("base_dn", models.CharField(blank=True, default="", max_length=512)),
                ("bind_dn", models.CharField(blank=True, default="", max_length=512)),
                ("bind_password_encrypted", models.TextField(blank=True, default="")),
                ("require_group_dn", models.CharField(blank=True, default="", max_length=512)),
                ("deny_group_dn", models.CharField(blank=True, default="", max_length=512)),
                ("staff_group_dns", models.JSONField(blank=True, default=list)),
                ("superuser_group_dns", models.JSONField(blank=True, default=list)),
                ("group_search_dn", models.CharField(blank=True, default="", max_length=512)),
                ("group_object_class", models.CharField(blank=True, default="group", max_length=64)),
                ("group_name_attr", models.CharField(blank=True, default="cn", max_length=64)),
                ("mirror_groups", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "accounts_ad_configuration",
            },
        ),
    ]

