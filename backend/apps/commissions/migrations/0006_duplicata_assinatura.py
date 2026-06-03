from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commissions", "0005_periodos_e_nf_comissao"),
    ]

    operations = [
        migrations.CreateModel(
            name="DuplicataAssinatura",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("estab", models.IntegerField()),
                ("pessoa", models.CharField(blank=True, default="", max_length=255)),
                ("cnpjf", models.BigIntegerField(blank=True, null=True)),
                ("docto", models.BigIntegerField()),
                ("parcela", models.IntegerField()),
                ("local", models.CharField(blank=True, default="", max_length=100)),
                ("assinada", models.BooleanField(db_index=True, default=False)),
                ("representante", models.CharField(blank=True, default="", max_length=255)),
                ("dtemissao", models.DateField(blank=True, null=True)),
                ("dtvencto", models.DateField(blank=True, null=True)),
                ("seqitem", models.IntegerField()),
                ("item", models.CharField(blank=True, default="", max_length=255)),
                ("grupocomissao", models.CharField(blank=True, default="", max_length=255)),
                ("comissaopercent", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("tabprc", models.IntegerField(blank=True, null=True)),
                ("tabela", models.CharField(blank=True, default="", max_length=255)),
                ("vlr_proporcional_item", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("previsao_comissao", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("comissao_paga", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
            ],
            options={
                "ordering": ["-dtvencto", "-docto", "parcela", "seqitem"],
            },
        ),
        migrations.AddConstraint(
            model_name="duplicataassinatura",
            constraint=models.UniqueConstraint(fields=("estab", "docto", "parcela", "seqitem"), name="uq_duplicata_assinatura_item"),
        ),
    ]

