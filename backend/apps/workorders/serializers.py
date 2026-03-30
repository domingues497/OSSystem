from rest_framework import serializers
from .models import WorkOrder, ERPNote

class WorkOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkOrder
        fields = "__all__"

class ERPNoteSerializer(serializers.ModelSerializer):
    created_by_name = serializers.ReadOnlyField(source='created_by.username')

    class Meta:
        model = ERPNote
        fields = ['id', 'cod_solicitacao', 'note', 'created_at', 'updated_at', 'created_by', 'created_by_name']
        read_only_fields = ['created_by']
