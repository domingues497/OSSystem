from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.conf import settings
from decimal import Decimal
from django.utils import timezone
import calendar

TIPO_CONTRATO_CHOICES = [
    ("CLT", "CLT"),
    ("PJ", "PJ"),
]

class Consultor(models.Model):
    nome = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    tipo_contrato = models.CharField(max_length=3, choices=TIPO_CONTRATO_CHOICES, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


PERIODO_STATUS_CHOICES = [
    ("aberto", "Aberto"),
    ("fechado", "Fechado"),
    ("faturado", "Faturado"),
    ("pago", "Pago"),
]


class PeriodoComissao(models.Model):
    referencia_ano = models.PositiveSmallIntegerField()
    referencia_mes = models.PositiveSmallIntegerField()
    data_inicial = models.DateField()
    data_final = models.DateField()
    status = models.CharField(max_length=10, choices=PERIODO_STATUS_CHOICES, default="aberto")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["referencia_ano", "referencia_mes"], name="uq_periodo_comissao_ref_mes"),
        ]
        ordering = ["-referencia_ano", "-referencia_mes"]

    def __str__(self):
        return f"{self.referencia_mes:02d}/{self.referencia_ano}"

    def clean(self):
        if not self.referencia_ano or not self.referencia_mes:
            raise ValidationError("Informe o mês/ano de referência.")
        if self.referencia_mes < 1 or self.referencia_mes > 12:
            raise ValidationError("Mês de referência inválido.")
        if not self.data_inicial or not self.data_final:
            raise ValidationError("Informe data inicial e final.")
        if self.data_inicial.day != 1:
            raise ValidationError("Período deve iniciar no dia 01.")
        if self.data_inicial.year != self.referencia_ano or self.data_inicial.month != self.referencia_mes:
            raise ValidationError("Data inicial deve corresponder ao mês/ano de referência.")
        last_day = calendar.monthrange(self.referencia_ano, self.referencia_mes)[1]
        expected_end = self.data_inicial.replace(day=last_day)
        if self.data_final != expected_end:
            raise ValidationError("Data final deve ser o último dia do mês de referência.")
        if self.data_final < self.data_inicial:
            raise ValidationError("Data final não pode ser menor que a data inicial.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ComissaoConsultorPeriodo(models.Model):
    consultor = models.ForeignKey(Consultor, on_delete=models.CASCADE, related_name="comissoes_periodo")
    periodo = models.ForeignKey(PeriodoComissao, on_delete=models.CASCADE, related_name="comissoes_consultores")
    valor_apurado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    data_fechamento = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=PERIODO_STATUS_CHOICES, default="aberto")
    observacoes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["consultor", "periodo"], name="uq_comissao_consultor_periodo"),
        ]
        ordering = ["-periodo__referencia_ano", "-periodo__referencia_mes", "consultor__nome"]

    def __str__(self):
        return f"{self.consultor} · {self.periodo} · R$ {self.valor_apurado}"

    def clean(self):
        if self.valor_apurado is None:
            raise ValidationError("Informe o valor apurado.")
        if Decimal(self.valor_apurado) < 0:
            raise ValidationError("Valor apurado não pode ser negativo.")
        if self.status in ("fechado", "faturado", "pago") and not self.data_fechamento:
            self.data_fechamento = timezone.now()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


NOTA_STATUS_CHOICES = [
    ("ativa", "Ativa"),
    ("cancelada", "Cancelada"),
    ("paga", "Paga"),
]


class NotaFiscalComissao(models.Model):
    comissao = models.ForeignKey(ComissaoConsultorPeriodo, on_delete=models.CASCADE, related_name="notas_fiscais")
    numero_nota = models.CharField(max_length=50)
    data_emissao = models.DateField()
    valor_nota = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=NOTA_STATUS_CHOICES, default="ativa")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["numero_nota"], name="uq_nf_comissao_numero"),
            models.UniqueConstraint(
                fields=["comissao"],
                condition=Q(status__in=["ativa", "paga"]),
                name="uq_nf_comissao_ativa_por_comissao",
            ),
        ]
        ordering = ["-data_emissao", "-created_at"]

    def __str__(self):
        return f"NF {self.numero_nota} · {self.comissao.consultor} · {self.comissao.periodo}"

    def clean(self):
        if not self.comissao_id:
            raise ValidationError("Informe a comissão do consultor no período.")
        if not self.data_emissao:
            raise ValidationError("Informe a data de emissão.")
        if self.comissao.status not in ("fechado", "faturado", "pago"):
            raise ValidationError("Não é permitido cadastrar nota fiscal sem comissão fechada para o período.")
        if self.valor_nota is None:
            raise ValidationError("Informe o valor da nota.")
        v1 = Decimal(self.valor_nota).quantize(Decimal("0.01"))
        v2 = Decimal(self.comissao.valor_apurado).quantize(Decimal("0.01"))
        if v1 != v2:
            raise ValidationError("Valor da nota deve ser exatamente igual ao valor da comissão apurada no período.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Comissao(models.Model):
    consultor = models.ForeignKey(Consultor, on_delete=models.CASCADE, related_name='comissoes')
    valor_total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comissão de {self.consultor.nome} - R$ {self.valor_total}"

    @property
    def valor_recebido(self):
        result = self.recebimentos.aggregate(total=Sum('valor_pago'))['total']
        return result or Decimal('0.00')

    @property
    def saldo_pendente(self):
        return self.valor_total - self.valor_recebido

class Recebimento(models.Model):
    comissao = models.ForeignKey(Comissao, on_delete=models.CASCADE, related_name='recebimentos')
    numero_nota = models.CharField(max_length=50, unique=True)
    valor_pago = models.DecimalField(max_digits=12, decimal_places=2)
    data_nota = models.DateField()
    descricao = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.valor_pago <= 0:
            raise ValidationError("O valor pago deve ser maior que zero.")
        # Validar saldo apenas na criação para não quebrar edições sem recálculo complexo
        if not self.pk:
            if self.valor_pago > self.comissao.saldo_pendente:
                raise ValidationError(
                    f"Valor pago (R$ {self.valor_pago}) excede o saldo pendente (R$ {self.comissao.saldo_pendente})."
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"NF {self.numero_nota} - R$ {self.valor_pago}"


class AuditLog(models.Model):
    action = models.CharField(max_length=50)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs")
    entity_type = models.CharField(max_length=100)
    entity_id = models.PositiveBigIntegerField()
    data = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id}"
