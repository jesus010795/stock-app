from django.urls import path
from . import views

app_name = "products"

urlpatterns = [
    # path("", views.MovimientoListView.as_view(), name="historial"),
    path("lista/", views.ProductListView.as_view(), name="products_list"),
    # path("<int:pk>/", views.MovimientoDetailView.as_view(), name="detalle"),
]
