from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commissions", "0003_comissao_tipo_contrato"),
    ]

    operations = [
        migrations.AddField(
            model_name="consultor",
            name="tipo_contrato",
            field=models.CharField(
                blank=True,
                choices=[("CLT", "CLT"), ("PJ", "PJ")],
                db_index=True,
                max_length=3,
                null=True,
            ),
        ),
        migrations.RemoveField(
            model_name="comissao",
            name="tipo_contrato",
        ),
    ]

