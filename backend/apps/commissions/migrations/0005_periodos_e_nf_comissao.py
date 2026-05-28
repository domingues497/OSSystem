from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("commissions", "0004_move_tipo_contrato_to_consultor"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PeriodoComissao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("referencia_ano", models.PositiveSmallIntegerField()),
                ("referencia_mes", models.PositiveSmallIntegerField()),
                ("data_inicial", models.DateField()),
                ("data_final", models.DateField()),
                ("status", models.CharField(choices=[("aberto", "Aberto"), ("fechado", "Fechado"), ("faturado", "Faturado"), ("pago", "Pago")], default="aberto", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-referencia_ano", "-referencia_mes"],
            },
        ),
        migrations.CreateModel(
            name="ComissaoConsultorPeriodo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("valor_apurado", models.DecimalField(decimal_places=2, default="0.00", max_digits=12)),
                ("data_fechamento", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("aberto", "Aberto"), ("fechado", "Fechado"), ("faturado", "Faturado"), ("pago", "Pago")], default="aberto", max_length=10)),
                ("observacoes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("consultor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comissoes_periodo", to="commissions.consultor")),
                ("periodo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comissoes_consultores", to="commissions.periodocomissao")),
            ],
            options={
                "ordering": ["-periodo__referencia_ano", "-periodo__referencia_mes", "consultor__nome"],
            },
        ),
        migrations.CreateModel(
            name="NotaFiscalComissao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero_nota", models.CharField(max_length=50)),
                ("data_emissao", models.DateField()),
                ("valor_nota", models.DecimalField(decimal_places=2, max_digits=12)),
                ("status", models.CharField(choices=[("ativa", "Ativa"), ("cancelada", "Cancelada"), ("paga", "Paga")], default="ativa", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("comissao", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notas_fiscais", to="commissions.comissaoconsultorperiodo")),
            ],
            options={
                "ordering": ["-data_emissao", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="periodocomissao",
            constraint=models.UniqueConstraint(fields=("referencia_ano", "referencia_mes"), name="uq_periodo_comissao_ref_mes"),
        ),
        migrations.AddConstraint(
            model_name="comissaoconsultorperiodo",
            constraint=models.UniqueConstraint(fields=("consultor", "periodo"), name="uq_comissao_consultor_periodo"),
        ),
        migrations.AddConstraint(
            model_name="notafiscalcomissao",
            constraint=models.UniqueConstraint(fields=("numero_nota",), name="uq_nf_comissao_numero"),
        ),
        migrations.AddConstraint(
            model_name="notafiscalcomissao",
            constraint=models.UniqueConstraint(condition=models.Q(("status__in", ["ativa", "paga"])), fields=("comissao",), name="uq_nf_comissao_ativa_por_comissao"),
        ),
    ]

