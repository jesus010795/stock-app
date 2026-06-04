from django.contrib import admin
from django.db import models
from .models import Department, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "employee_count", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["name"]
    readonly_fields = ["created_at"]

    fieldsets = (
        ("Información Principal", {"fields": ("name", "description")}),
        ("Metadatos", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _employee_count=models.Count(
                "employees", filter=models.Q(employees__is_active=True)
            )
        )

    def employee_count(self, obj):
        return getattr(obj, "_employee_count", 0)

    employee_count.short_description = "Empleados Activos"


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = [
        "last_name",
        "first_name",
        "department",
        "is_active",
        "created_at",
        "created_by",
    ]
    list_filter = ["department", "is_active"]
    search_fields = ["first_name", "last_name"]
    ordering = ["last_name", "first_name"]
    list_editable = ["is_active"]
    list_per_page = 25
    readonly_fields = ["created_at", "created_by"]

    fieldsets = (
        ("Información Personal", {"fields": ("first_name", "last_name")}),
        ("Departamento", {"fields": ("department",)}),
        ("Estado", {"fields": ("is_active",)}),
        (
            "Metadatos",
            {"fields": ("created_at", "created_by"), "classes": ("collapse",)},
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
