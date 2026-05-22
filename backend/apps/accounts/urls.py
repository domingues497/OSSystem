from django.urls import path
from .views import RegisterView, MeView, ADConfigView, ADTestConnectionView, ADGroupsView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("ad/config/", ADConfigView.as_view(), name="ad_config"),
    path("ad/test/", ADTestConnectionView.as_view(), name="ad_test"),
    path("ad/groups/", ADGroupsView.as_view(), name="ad_groups"),
]
