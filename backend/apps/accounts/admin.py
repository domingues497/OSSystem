from django.contrib import admin
from .models import ADConfiguration, Feature, Menu, MenuItem, ImportProfile, InternalField


@admin.register(ADConfiguration)
class ADConfigurationAdmin(admin.ModelAdmin):
    list_display = ["id", "host", "port", "use_ssl", "base_dn", "updated_at"]


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active", "created_at"]
    search_fields = ["code", "name"]
    list_filter = ["is_active"]
    filter_horizontal = ["users", "groups"]


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0
    fields = ["title", "path", "order", "is_active", "parent", "feature"]
    ordering = ["order", "title"]


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ["title", "order", "is_active", "created_at"]
    search_fields = ["title"]
    list_filter = ["is_active"]
    filter_horizontal = ["users", "groups"]
    inlines = [MenuItemInline]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ["title", "menu", "path", "order", "is_active", "parent", "feature"]
    search_fields = ["title", "path"]
    list_filter = ["is_active", "menu"]
    filter_horizontal = ["users", "groups"]


@admin.register(ImportProfile)
class ImportProfileAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "source_type", "source_identifier", "is_active", "updated_at"]
    search_fields = ["code", "name", "source_identifier"]
    list_filter = ["is_active", "source_type"]


@admin.register(InternalField)
class InternalFieldAdmin(admin.ModelAdmin):
    list_display = ["key", "label", "required", "order", "is_active", "updated_at"]
    search_fields = ["key", "label"]
    list_filter = ["is_active", "required"]
