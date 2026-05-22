from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from .models import Consultor, Comissao, Recebimento, AuditLog
from .serializers import ConsultorSerializer, ComissaoSerializer, RecebimentoSerializer
from django.core.exceptions import ValidationError

@login_required
@ensure_csrf_cookie
def dashboard_view(request):
    return render(request, 'commissions/dashboard.html')

def _log_action(request, action, instance, data):
    try:
        ip = None
        user_agent = ""
        actor = None
        if request is not None:
            try:
                ip = request.META.get("REMOTE_ADDR")
            except Exception:
                ip = None
            try:
                user_agent = str(request.META.get("HTTP_USER_AGENT") or "")
            except Exception:
                user_agent = ""
            try:
                actor = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
            except Exception:
                actor = None
        AuditLog.objects.create(
            action=str(action),
            actor=actor,
            entity_type=instance.__class__.__name__,
            entity_id=int(instance.pk),
            data=data or {},
            ip_address=ip,
            user_agent=user_agent,
        )
    except Exception:
        return

class ConsultorViewSet(viewsets.ModelViewSet):
    queryset = Consultor.objects.all()
    serializer_class = ConsultorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        _log_action(
            request,
            "consultor.create",
            instance,
            {"nome": instance.nome, "email": instance.email, "telefone": instance.telefone},
        )
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class ComissaoViewSet(viewsets.ModelViewSet):
    queryset = Comissao.objects.select_related('consultor').prefetch_related('recebimentos').all()
    serializer_class = ComissaoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        _log_action(
            request,
            "comissao.create",
            instance,
            {"consultor_id": instance.consultor_id, "valor_total": str(instance.valor_total)},
        )
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class RecebimentoViewSet(viewsets.ModelViewSet):
    queryset = Recebimento.objects.all()
    serializer_class = RecebimentoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
            instance = serializer.instance
            _log_action(
                request,
                "recebimento.create",
                instance,
                {
                    "comissao_id": instance.comissao_id,
                    "numero_nota": instance.numero_nota,
                    "valor_pago": str(instance.valor_pago),
                    "data_nota": instance.data_nota.isoformat() if instance.data_nota else None,
                    "descricao": instance.descricao,
                },
            )
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except ValidationError as e:
            return Response({"error": e.messages}, status=status.HTTP_400_BAD_REQUEST)
