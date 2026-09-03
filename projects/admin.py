from django.contrib import admin
from .models import Project
from inventory.models import Movement, MovementType


class ConsumedProductsInline(admin.TabularInline):
    model = Movement
    extra = 0
    readonly_fields = ['product', 'quantity', 'created_at']
    verbose_name = "Producto Consumido"
    verbose_name_plural = "Productos Consumidos"

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(movement_type=MovementType.EXIT).select_related('product', 'product__unit')
        return qs


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name",
        "status",
        "product_count",
        "total_consumption",
        "start_date",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["code", "name", "description", "client"]
    ordering = ["code"]
    list_editable = ["status"]
    readonly_fields = ["product_count", "total_consumption", "created_at"]
    inlines = [ConsumedProductsInline]

    fieldsets = (
        ("Información Principal", {"fields": ("code", "name", "client", "description")}),
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
        return super().get_queryset(request).with_consumption()

    def product_count(self, obj):
        return getattr(obj, "_product_count", 0)

    product_count.short_description = "Productos Distintos"
    product_count.admin_order_field = "_product_count"

    def total_consumption(self, obj):
        return getattr(obj, "_total_qty", 0) or 0

    total_consumption.short_description = "Cant. Total Salidas"
    total_consumption.admin_order_field = "_total_qty"
