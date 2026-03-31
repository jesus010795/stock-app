from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'product_count', 'total_consumption', 'created_at']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'description']
    ordering = ['code']
    list_editable = ['is_active']
    readonly_fields = ['product_count', 'total_consumption', 'created_at']
    
    fieldsets = (
        ('Información Principal', {
            'fields': ('code', 'name', 'description')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
        ('Estadísticas', {
            'fields': ('product_count', 'total_consumption', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def product_count(self, obj):
        return obj.product_count
    product_count.short_description = 'Productos Consumidos'

    def total_consumption(self, obj):
        return obj.total_consumption
    total_consumption.short_description = 'Consumo Total'