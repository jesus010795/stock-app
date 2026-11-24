from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.MovementListView.as_view(), name="historial"),
    path("nuevo/", views.MovementCreateView.as_view(), name="nuevo"),
    path(
        "productos/buscar/",
        views.product_search,
        name="product-search",
    ),
    path(
        "empleados/buscar/",
        views.employee_search,
        name="employee-search",
    ),
    path(
        "proyectos/buscar/",
        views.project_search,
        name="project-search",
    ),
    path("<int:pk>/", views.MovementDetailView.as_view(), name="detalle"),
]
