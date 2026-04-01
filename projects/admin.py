from django.contrib import admin
from .models import Project
from django.db.models import Sum, Count, Q


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name",
        "status",
        "product_count",
        "total_consumption",
        "start_date",
    ]
    list_filter = ["status"]
    search_fields = ["code", "name", "description"]
    ordering = ["code"]
    list_editable = ["status"]
    readonly_fields = ["product_count", "total_consumption", "created_at"]

    fieldsets = (
        ("Información Principal", {"fields": ("code", "name", "description")}),
        ("Cronología", {"fields": ("start_date", "end_date")}),
        ("Estado", {"fields": ("status",)}),
        (
            "Estadísticas",
            {
                "fields": ("product_count", "total_consumption", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _product_count=Count("movements__product", distinct=True),
            _total_qty=Sum(
                "movements__quantity", filter=Q(movements__movement_type="EXIT")
            ),
        )
        return queryset

    def product_count(self, obj):
        return getattr(obj, "_product_count", 0)

    product_count.short_description = "Productos Distintos"
    product_count.admin_order_field = "_product_count"

    def total_consumption(self, obj):
        return getattr(obj, "_total_qty", 0) or 0

    total_consumption.short_description = "Cant. Total Salidas"
    total_consumption.admin_order_field = "_total_qty"
