from rest_framework import serializers
from .models import Consultor, Comissao, Recebimento, PeriodoComissao, ComissaoConsultorPeriodo, NotaFiscalComissao

class ConsultorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultor
        fields = '__all__'

class RecebimentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recebimento
        fields = '__all__'

class ComissaoSerializer(serializers.ModelSerializer):
    consultor = ConsultorSerializer(read_only=True)
    consultor_id = serializers.PrimaryKeyRelatedField(source="consultor", queryset=Consultor.objects.all(), write_only=True)
    recebimentos = serializers.SerializerMethodField()
    valor_recebido = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    saldo_pendente = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    def get_recebimentos(self, obj):
        request = self.context.get("request") if isinstance(self.context, dict) else None
        user = getattr(request, "user", None) if request is not None else None
        if user and user.is_authenticated and user.has_perm("commissions.view_recebimento"):
            qs = getattr(obj, "recebimentos", None)
            items = qs.all() if qs is not None else []
            return RecebimentoSerializer(items, many=True).data
        return []

    class Meta:
        model = Comissao
        fields = ['id', 'consultor', 'consultor_id', 'valor_total', 'valor_recebido', 'saldo_pendente', 'recebimentos', 'created_at']


class PeriodoComissaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodoComissao
        fields = "__all__"


class ComissaoConsultorPeriodoSerializer(serializers.ModelSerializer):
    consultor = ConsultorSerializer(read_only=True)
    consultor_id = serializers.PrimaryKeyRelatedField(source="consultor", queryset=Consultor.objects.all(), write_only=True)
    periodo = PeriodoComissaoSerializer(read_only=True)
    periodo_id = serializers.PrimaryKeyRelatedField(source="periodo", queryset=PeriodoComissao.objects.all(), write_only=True)

    class Meta:
        model = ComissaoConsultorPeriodo
        fields = [
            "id",
            "consultor",
            "consultor_id",
            "periodo",
            "periodo_id",
            "valor_apurado",
            "data_fechamento",
            "status",
            "observacoes",
            "created_at",
        ]


class NotaFiscalComissaoSerializer(serializers.ModelSerializer):
    comissao = ComissaoConsultorPeriodoSerializer(read_only=True)
    comissao_id = serializers.PrimaryKeyRelatedField(source="comissao", queryset=ComissaoConsultorPeriodo.objects.all(), write_only=True)

    class Meta:
        model = NotaFiscalComissao
        fields = [
            "id",
            "comissao",
            "comissao_id",
            "numero_nota",
            "data_emissao",
            "valor_nota",
            "status",
            "created_at",
        ]
