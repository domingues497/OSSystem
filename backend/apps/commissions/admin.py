from django.contrib import admin
from .models import Consultor, Comissao, Recebimento, AuditLog


@admin.register(Consultor)
class ConsultorAdmin(admin.ModelAdmin):
    search_fields = ["nome", "email", "telefone"]
    list_display = ["id", "nome", "email", "telefone", "created_at"]


@admin.register(Comissao)
class ComissaoAdmin(admin.ModelAdmin):
    search_fields = ["consultor__nome", "consultor__email"]
    list_display = ["id", "consultor", "valor_total", "created_at"]
    list_select_related = ["consultor"]


@admin.register(Recebimento)
class RecebimentoAdmin(admin.ModelAdmin):
    search_fields = ["numero_nota", "comissao__consultor__nome"]
    list_display = ["id", "numero_nota", "comissao", "valor_pago", "data_nota", "created_at"]
    list_select_related = ["comissao", "comissao__consultor"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    search_fields = ["action", "entity_type", "entity_id", "actor__username"]
    list_display = ["id", "action", "entity_type", "entity_id", "actor", "ip_address", "created_at"]
    list_filter = ["action", "entity_type", "created_at"]
    readonly_fields = ["action", "entity_type", "entity_id", "actor", "data", "ip_address", "user_agent", "created_at"]
