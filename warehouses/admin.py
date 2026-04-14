from django.contrib import admin
from .models import Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "warehouse_type", "location", "is_active", "created_at"]
    list_filter = ["warehouse_type", "is_active"]
    search_fields = ["code", "name", "location"]
    ordering = ["code"]
    list_editable = ["is_active"]

    fieldsets = (
        ("Información Principal", {"fields": ("code", "name", "description")}),
        ("Tipo y Ubicación", {"fields": ("warehouse_type", "location")}),
        ("Estado", {"fields": ("is_active",)}),
    )