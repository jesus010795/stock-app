from django.views.generic import DetailView, ListView
from .models import Project


class ProjectListView(ListView):
    model = Project
    template_name = "projects/project_list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return Project.objects.with_consumption()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumb_title"] = "Proyectos"
        return context


class ProjectDetailView(DetailView):
    model = Project
    template_name = "projects/project_detail.html"
    context_object_name = "project"
    queryset = Project.objects.with_consumption()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        context["breadcrumb_title"] = project.name
        context["movement_count"] = project.total_movements()
        context["recent_movements"] = project.recent_movements(limit=10)
        context["involved_employees"] = project.involved_employees(limit=5)
        context["exit_groups"] = project.exit_groups_by_employee()
        return context