from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    # path("", views.MovimientoListView.as_view(), name="historial"),
    path("nuevo/", views.MovementCreateView.as_view(), name="nuevo"),
    # path("<int:pk>/", views.MovimientoDetailView.as_view(), name="detalle"),
]
