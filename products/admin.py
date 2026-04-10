from django.contrib import admin
from .models import Category, Unit, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "product_count", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    ordering = ["name"]
    list_editable = ["is_active"]
    readonly_fields = ["product_count", "created_at"]

    fieldsets = (
        ("Información Principal", {"fields": ("name", "description")}),
        ("Estado", {"fields": ("is_active",)}),
        ("Metadatos", {"fields": ("product_count", "created_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).with_product_count()

    def product_count(self, obj):
        return getattr(obj, "_product_count", 0)

    product_count.short_description = "Productos"


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["name", "abbreviation", "is_active", "product_count", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "abbreviation"]
    ordering = ["name"]
    list_editable = ["is_active"]
    readonly_fields = ["product_count", "created_at"]

    fieldsets = (
        ("Información Principal", {"fields": ("name", "abbreviation")}),
        ("Estado", {"fields": ("is_active",)}),
        ("Metadatos", {"fields": ("product_count", "created_at"), "classes": ("collapse",)}),
    )

    def product_count(self, obj):
        return obj.products.count()

    product_count.short_description = "Productos"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["sku", "name", "category", "unit", "current_stock", "minimum_stock", "is_active"]
    list_filter = ["category", "unit", "is_active"]
    search_fields = ["sku", "name"]
    ordering = ["sku", "name"]
    list_editable = ["is_active"]
    list_per_page = 25

    fieldsets = (
        ("Información Principal", {"fields": ("sku", "name", "description")}),
        ("Clasificación", {"fields": ("category", "unit")}),
        ("Stock", {"fields": ("minimum_stock",)}),
        ("Estado", {"fields": ("is_active",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).with_stock().with_category()

    def current_stock(self, obj):
        return getattr(obj, "_stock", 0)

    current_stock.short_description = "Stock Actual"
    current_stock.admin_order_field = "_stock"
