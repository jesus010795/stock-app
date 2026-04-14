from django.contrib import admin
from .models import Movement


@admin.register(Movement)
class MovementAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "product",
        "movement_type",
        "signed_quantity",
        "warehouse",
        "project",
        "reason",
    ]
    list_filter = [
        "movement_type",
        "adjustment_type",
        "warehouse",
        ("created_at", admin.DateFieldListFilter),
        "product__category",
        "project",
    ]
    search_fields = [
        "product__sku",
        "product__name",
        "project__code",
        "project__name",
        "reason",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    list_per_page = 20

    readonly_fields = ["created_at", "created_by"]

    fieldsets = (
        ("Producto", {"fields": ("product",)}),
        ("Tipo de Movimiento", {"fields": ("movement_type", "adjustment_type")}),
        ("Cantidad", {"fields": ("quantity",)}),
        (
            "Ubicación",
            {
                "fields": ("warehouse",),
            },
        ),
        (
            "Justificación",
            {
                "fields": ("project", "reason"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at", "created_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def signed_quantity(self, obj):
        signed = obj.signed_quantity
        if signed >= 0:
            return f"+{signed}"
        return f"{signed}"

    signed_quantity.short_description = "Cantidad"

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + [
                "product",
                "movement_type",
                "quantity",
                "adjustment_type",
                "project",
                "reason",
            ]
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
