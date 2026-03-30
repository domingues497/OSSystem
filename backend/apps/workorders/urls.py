from rest_framework.routers import DefaultRouter
from .views import WorkOrderViewSet, ERPNoteViewSet

router = DefaultRouter()
router.register(r"erp-notes", ERPNoteViewSet, basename="erp-note")
router.register(r"", WorkOrderViewSet, basename="workorder")
urlpatterns = router.urls
