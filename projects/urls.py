from django.urls import path
from . import views

app_name = "projects"

urlpatterns = [
    # path("", views.MovimientoListView.as_view(), name="historial"),
    path("lista/", views.ProjectListView.as_view(), name="projects_list"),
    # path("<int:pk>/", views.MovimientoDetailView.as_view(), name="detalle"),
]
