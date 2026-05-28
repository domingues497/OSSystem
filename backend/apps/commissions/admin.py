from django.contrib import admin
from .models import Consultor, Comissao, Recebimento, AuditLog, PeriodoComissao, ComissaoConsultorPeriodo, NotaFiscalComissao


@admin.register(Consultor)
class ConsultorAdmin(admin.ModelAdmin):
    search_fields = ["nome", "email", "telefone"]
    list_display = ["id", "nome", "tipo_contrato", "email", "telefone", "created_at"]
    list_filter = ["tipo_contrato", "created_at"]


@admin.register(Comissao)
class ComissaoAdmin(admin.ModelAdmin):
    search_fields = ["consultor__nome", "consultor__email"]
    list_display = ["id", "consultor", "valor_total", "created_at"]
    list_select_related = ["consultor"]
    list_filter = ["created_at"]


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


@admin.register(PeriodoComissao)
class PeriodoComissaoAdmin(admin.ModelAdmin):
    list_display = ["id", "referencia_mes", "referencia_ano", "data_inicial", "data_final", "status", "created_at"]
    list_filter = ["status", "referencia_ano"]
    search_fields = ["referencia_ano", "referencia_mes"]


@admin.register(ComissaoConsultorPeriodo)
class ComissaoConsultorPeriodoAdmin(admin.ModelAdmin):
    list_display = ["id", "consultor", "periodo", "status", "valor_apurado", "data_fechamento", "created_at"]
    list_filter = ["status", "periodo__referencia_ano", "periodo__referencia_mes", "consultor__tipo_contrato"]
    search_fields = ["consultor__nome", "consultor__email"]
    list_select_related = ["consultor", "periodo"]


@admin.register(NotaFiscalComissao)
class NotaFiscalComissaoAdmin(admin.ModelAdmin):
    list_display = ["id", "numero_nota", "comissao", "data_emissao", "valor_nota", "status", "created_at"]
    list_filter = ["status", "data_emissao"]
    search_fields = ["numero_nota", "comissao__consultor__nome"]
    list_select_related = ["comissao", "comissao__consultor", "comissao__periodo"]
