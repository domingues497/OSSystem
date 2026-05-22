from django.db import migrations, models


def _forwards(apps, schema_editor):
    ADConfiguration = apps.get_model("accounts", "ADConfiguration")
    try:
        cfg = ADConfiguration.objects.get(id=1)
    except Exception:
        return
    require = (getattr(cfg, "require_group_dn", "") or "").strip()
    deny = (getattr(cfg, "deny_group_dn", "") or "").strip()
    if require and not (getattr(cfg, "require_group_dns", None) or []):
        cfg.require_group_dns = [require]
    if deny and not (getattr(cfg, "deny_group_dns", None) or []):
        cfg.deny_group_dns = [deny]
    cfg.save(update_fields=["require_group_dns", "deny_group_dns"])


def _backwards(apps, schema_editor):
    ADConfiguration = apps.get_model("accounts", "ADConfiguration")
    try:
        cfg = ADConfiguration.objects.get(id=1)
    except Exception:
        return
    req = (getattr(cfg, "require_group_dns", None) or [])
    den = (getattr(cfg, "deny_group_dns", None) or [])
    cfg.require_group_dn = str(req[0]) if req else ""
    cfg.deny_group_dn = str(den[0]) if den else ""
    cfg.save(update_fields=["require_group_dn", "deny_group_dn"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="adconfiguration",
            name="require_group_dns",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="adconfiguration",
            name="deny_group_dns",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(_forwards, _backwards),
    ]
