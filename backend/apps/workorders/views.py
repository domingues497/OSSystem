from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import connections
from .models import WorkOrder, ERPNote
from .serializers import WorkOrderSerializer, ERPNoteSerializer

class WorkOrderViewSet(viewsets.ModelViewSet):
    queryset = WorkOrder.objects.all()
    serializer_class = WorkOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

class ERPNoteViewSet(viewsets.ModelViewSet):
    queryset = ERPNote.objects.all()
    serializer_class = ERPNoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], url_path='erp-chamado/(?P<cod_solicitacao>[^/.]+)')
    def get_erp_data(self, request, cod_solicitacao=None):
        """
        Busca dados do chamado diretamente no banco PostgreSQL do ERP
        e anexa as anotações locais do SQLite.
        """
        try:
            with connections['erp'].cursor() as cursor:
                # Consulta principal (DM1744)
                cursor.execute("""
                    SELECT 
                        DM1744.PRIORIDADE, 
                        DM1744.COD_STATUS_DOC, 
                        DM1744.DATA_CAD, 
                        DS0300.NOME_USUARIO as SOLICITANTE,
                        DM1744.COD_SOLICITACAO, 
                        DM1744.TITULO_SOLICITACAO,
                        DC1629.DESCR_ATIVO
                    FROM BANCO01.DM1744 
                    LEFT JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1744.COD_USUARIO)
                    LEFT JOIN BANCO01.DC1629 ON (DC1629.COD_ATIVO = DM1744.COD_ATIVO)
                    WHERE DM1744.COD_SOLICITACAO = %s
                """, [cod_solicitacao])
                
                row = cursor.fetchone()
                if not row:
                    return Response({"error": "Chamado não encontrado no ERP"}, status=status.HTTP_404_NOT_FOUND)

                columns = [col[0].lower() for col in cursor.description]
                erp_data = dict(zip(columns, row))

                # Busca o último comentário (DM1745)
                cursor.execute("""
                    SELECT 
                        A.DATA_GRAV, A.HORA_GRAV, U.NOME_USUARIO, A.DESCR_ACOMP
                    FROM BANCO01.DM1745 A
                    INNER JOIN public.DS0300 U ON (U.COD_USUARIO = A.COD_USUARIO)
                    WHERE A.COD_SOLICITACAO = %s 
                      AND A.COD_USUARIO > 0
                    ORDER BY A.DATA_GRAV DESC, A.HORA_GRAV DESC
                    LIMIT 1
                """, [cod_solicitacao])
                
                last_comment = cursor.fetchone()
                if last_comment:
                    erp_data['ultimo_comentario_erp'] = {
                        "data": last_comment[0],
                        "hora": last_comment[1],
                        "usuario": last_comment[2],
                        "texto": last_comment[3]
                    }

            # Busca anotações locais (SQLite)
            local_notes = ERPNote.objects.filter(cod_solicitacao=cod_solicitacao)
            erp_data['anotacoes_locais'] = ERPNoteSerializer(local_notes, many=True).data

            return Response(erp_data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
