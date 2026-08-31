from django.views.generic import ListView
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