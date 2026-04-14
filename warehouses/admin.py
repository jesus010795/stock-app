from django.contrib import admin
from .models import Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "warehouse_type", "location", "product_count", "is_active", "created_at"]
    list_filter = ["warehouse_type", "is_active"]
    search_fields = ["code", "name", "location"]
    ordering = ["code"]
    list_editable = ["is_active"]
    readonly_fields = ["product_count", "created_at"]

    fieldsets = (
        ("Información Principal", {"fields": ("code", "name", "description")}),
        ("Tipo y Ubicación", {"fields": ("warehouse_type", "location")}),
        ("Estado", {"fields": ("is_active",)}),
        ("Metadatos", {"fields": ("product_count", "created_at"), "classes": ("collapse",)}),
    )

    def product_count(self, obj):
        return obj.products.count()

    product_count.short_description = "Productos"