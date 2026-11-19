from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.MovementListView.as_view(), name="historial"),
    path("nuevo/", views.MovementCreateView.as_view(), name="nuevo"),
    path(
        "productos/buscar/",
        views.buscar_productos,
        name="buscar-productos",
    ),
    path("<int:pk>/", views.MovementDetailView.as_view(), name="detalle"),
]
