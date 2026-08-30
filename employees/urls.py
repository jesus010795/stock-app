from django.urls import path
from . import views

app_name = "employees"

urlpatterns = [
    path("lista/", views.EmployeeListView.as_view(), name="employees_list"),
]