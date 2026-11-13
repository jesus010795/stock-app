from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.MovementListView.as_view(), name="historial"),
    path("nuevo/", views.MovementCreateView.as_view(), name="nuevo"),
    path("<int:pk>/", views.MovementDetailView.as_view(), name="detalle"),
]
