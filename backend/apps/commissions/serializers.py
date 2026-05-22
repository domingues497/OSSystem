from rest_framework import serializers
from .models import Consultor, Comissao, Recebimento

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
    recebimentos = RecebimentoSerializer(many=True, read_only=True)
    valor_recebido = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    saldo_pendente = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Comissao
        fields = ['id', 'consultor', 'consultor_id', 'valor_total', 'valor_recebido', 'saldo_pendente', 'recebimentos', 'created_at']
