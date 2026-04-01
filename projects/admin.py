from django.contrib import admin
from .models import Project
from django.db.models import Sum, Count, Q


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name",
        "is_active",
        "product_count",
        "total_consumption",
        "created_at",
    ]
    list_filter = ["is_active"]
    search_fields = ["code", "name", "description"]
    ordering = ["code"]
    list_editable = ["is_active"]
    readonly_fields = ["product_count", "total_consumption", "created_at"]

    fieldsets = (
        ("Información Principal", {"fields": ("code", "name", "description")}),
        ("Estado", {"fields": ("is_active",)}),
        (
            "Estadísticas",
            {
                "fields": ("product_count", "total_consumption", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )

    # def product_count(self, obj):
    #     return obj.product_count
    # product_count.short_description = 'Productos Consumidos'

    # def total_consumption(self, obj):
    #     return obj.total_consumption
    # total_consumption.short_description = 'Consumo Total'

    def get_queryset(self, request):
        """
        Calculamos las estadísticas en UNA SOLA consulta SQL
        usando JOINs optimizados.
        """
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            # Contamos productos distintos
            _product_count=Count("movements__product", distinct=True),
            # Sumamos solo movimientos de tipo EXIT (Salida)
            _total_qty=Sum(
                "movements__quantity", filter=Q(movements__movement_type="EXIT")
            ),
        )
        return queryset

    def product_count(self, obj):
        # Usamos el valor anotado (o el de la property si falla)
        return getattr(obj, "_product_count", 0)

    product_count.short_description = "Productos Distintos"
    product_count.admin_order_field = (
        "_product_count"  # ¡Ahora puedes ordenar por esta columna!
    )

    def total_consumption(self, obj):
        return getattr(obj, "_total_qty", 0) or 0

    total_consumption.short_description = "Cant. Total Salidas"
    total_consumption.admin_order_field = "_total_qty"
