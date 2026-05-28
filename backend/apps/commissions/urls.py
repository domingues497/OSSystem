from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConsultorViewSet, ComissaoViewSet, RecebimentoViewSet, PeriodoComissaoViewSet, ComissaoConsultorPeriodoViewSet, NotaFiscalComissaoViewSet

router = DefaultRouter()
router.register(r'consultores', ConsultorViewSet)
router.register(r'comissoes', ComissaoViewSet)
router.register(r'recebimentos', RecebimentoViewSet)
router.register(r'periodos', PeriodoComissaoViewSet)
router.register(r'comissoes-periodo', ComissaoConsultorPeriodoViewSet)
router.register(r'notas-fiscais', NotaFiscalComissaoViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
