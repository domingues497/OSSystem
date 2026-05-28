from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import views as auth_views
from apps.accounts.views import ad_config_page, home_page, planejamento_safra_2627_page, access_control_page, viewprogramacao_api, import_mapping_page
from apps.commissions.views import dashboard_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_page, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/login/"), name="logout"),
    path("ad-config/", ad_config_page, name="ad_config_page"),
    path("access-control/", access_control_page, name="access_control"),
    path("access-control/<int:user_id>/", access_control_page, name="access_control_user"),
    path("import-mapping/", import_mapping_page, name="import_mapping"),
    path("import-mapping/<slug:code>/", import_mapping_page, name="import_mapping_code"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/customers/", include("apps.customers.urls")),
    path("api/workorders/", include("apps.workorders.urls")),
    path("api/commissions/", include("apps.commissions.urls")),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("planejamento/safra-2627/", planejamento_safra_2627_page, name="planejamento_safra_2627"),
    path("api/planejamento/viewprogramacao/", viewprogramacao_api, name="viewprogramacao_api"),
]
