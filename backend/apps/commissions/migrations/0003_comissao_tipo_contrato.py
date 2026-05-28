from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commissions", "0002_recebimento_descricao_recebimento_observacoes_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="comissao",
            name="tipo_contrato",
            field=models.CharField(
                blank=True,
                choices=[("CLT", "CLT"), ("PJ", "PJ")],
                db_index=True,
                max_length=3,
                null=True,
            ),
        ),
    ]

