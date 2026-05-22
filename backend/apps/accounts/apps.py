from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        from django.db.backends.signals import connection_created
        from django.dispatch import receiver
        from django.conf import settings

        @receiver(connection_created)
        def _set_search_path(sender, connection, **kwargs):
            schema = getattr(settings, "DJANGO_DB_SCHEMA", "capalti")
            if not schema:
                return
            if connection.alias != "default":
                return
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET search_path TO {schema}, public")
            except Exception:
                return
