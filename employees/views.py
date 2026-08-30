from django.views.generic import ListView
from .models import Department, Employee


class EmployeeListView(ListView):
    model = Employee
    template_name = "employees/employee_list.html"
    context_object_name = "employees"

    def get_queryset(self):
        return Employee.objects.select_related("department").with_consumption()


class DepartmentListView(ListView):
    model = Department
    template_name = "employees/department_list.html"
    context_object_name = "departments"

    def get_queryset(self):
        return Department.objects.with_employee_count()