from django.contrib import admin
from .models import Category, Unit, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_count', 'description']
    search_fields = ['name']
    ordering = ['name']

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Productos'


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['name', 'abbreviation', 'product_count']
    search_fields = ['name', 'abbreviation']
    ordering = ['name']

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Productos'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'category', 'unit', 'current_stock', 'is_active']
    list_filter = ['category', 'unit', 'is_active']
    search_fields = ['sku', 'name']
    ordering = ['sku', 'name']
    list_editable = ['is_active']
    list_per_page = 25

    fieldsets = (
        ('Información Principal', {
            'fields': ('sku', 'name', 'description')
        }),
        ('Clasificación', {
            'fields': ('category', 'unit')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )
