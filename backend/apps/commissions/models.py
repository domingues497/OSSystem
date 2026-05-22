from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.conf import settings
from decimal import Decimal

class Consultor(models.Model):
    nome = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

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
