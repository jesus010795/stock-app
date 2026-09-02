from django.views.generic import DetailView, ListView
from .models import Department, Employee


class EmployeeListView(ListView):
    model = Employee
    template_name = "employees/employee_list.html"
    context_object_name = "employees"

    def get_queryset(self):
        return Employee.objects.select_related("department").with_consumption()


class EmployeeDetailView(DetailView):
    model = Employee
    template_name = "employees/employee_detail.html"
    context_object_name = "employee"
    queryset = Employee.objects.select_related("department").with_consumption()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object
        context["breadcrumb_title"] = employee.full_name
        context["project_count"] = employee.consumed_projects().count()
        context["recent_movements"] = employee.recent_movements(limit=10)
        context["recent_projects"] = employee.consumed_projects(limit=5)
        context["exit_groups"] = employee.exit_groups()
        return context


class DepartmentListView(ListView):
    model = Department
    template_name = "employees/department_list.html"
    context_object_name = "departments"

    def get_queryset(self):
        return Department.objects.with_employee_count()