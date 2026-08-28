from django.shortcuts import render
from django.views.generic import ListView

from .models import Project


class ProjectListView(ListView):
    model = Project
    # template_name = "stock/product_list.html"  # La ruta donde estará tu archivo HTML
    context_object_name = (
        "projects"  # El nombre de la variable que usaremos en el template
    )
