from django.db import models
from django.contrib.auth.models import User
from apps.customers.models import Customer

class WorkOrder(models.Model):
    # ... existing choices ...
    STATUS_CHOICES = [
        ("aberta", "Aberta"),
        ("em_andamento", "Em andamento"),
        ("concluida", "Concluída"),
        ("cancelada", "Cancelada"),
    ]
    PRIORITY_CHOICES = [
        ("baixa", "Baixa"),
        ("media", "Média"),
        ("alta", "Alta"),
    ]
    number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="workorders")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="aberta")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="media")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_workorders")
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.number} - {self.title}"

class ERPNote(models.Model):
    cod_solicitacao = models.BigIntegerField(db_index=True) # ID do chamado no ERP (DM1744)
    note = models.TextField(verbose_name="Anotação Local")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Anotação de Chamado ERP"
        verbose_name_plural = "Anotações de Chamados ERP"
        ordering = ['-created_at']

    def __str__(self):
        return f"Nota Local - Chamado {self.cod_solicitacao}"
