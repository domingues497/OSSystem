from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import views as auth_views
from apps.accounts.views import ad_config_page
from apps.commissions.views import dashboard_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/login/"), name="logout"),
    path("ad-config/", ad_config_page, name="ad_config_page"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/customers/", include("apps.customers.urls")),
    path("api/workorders/", include("apps.workorders.urls")),
    path("api/commissions/", include("apps.commissions.urls")),
    path("dashboard/", dashboard_view, name="dashboard"),
]
