from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConsultorViewSet, ComissaoViewSet, RecebimentoViewSet

router = DefaultRouter()
router.register(r'consultores', ConsultorViewSet)
router.register(r'comissoes', ComissaoViewSet)
router.register(r'recebimentos', RecebimentoViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
