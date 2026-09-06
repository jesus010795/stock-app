from django.shortcuts import render
from django.views.generic import CreateView, TemplateView
from products.models import Product
from projects.models import Project
from .models import Movement
from .forms import MovementForm
from django.urls import reverse_lazy
from django.contrib import messages


# Create your views here.
class HomeView(TemplateView):
    template_name = "inventory/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["low_stock_products"] = Product.objects.low_stock()
        context["recent_movements"] = Movement.objects.recent(limit=10)
        context["recent_projects"] = Project.objects.recent(limit=5)
        context["recent_activity"] = Movement.get_recent_activity(limit=5)
        return context


class MovementCreateView(CreateView):
    model = Movement
    form_class = MovementForm
    template_name = "inventory/movimiento_form.html"
    success_url = reverse_lazy(
        "inventory:nuevo"
    )  # o "inventory:historial" cuando exista

    def get_initial(self):
        initial = super().get_initial()
        product_id = self.request.GET.get("producto")
        if product_id and Product.objects.filter(pk=product_id).exists():
            initial["product"] = product_id
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Movimiento registrado correctamente")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb_title"] = "Nuevo Movimiento"
        ctx["breadcrumb_subtitle"] = "Registrar entrada, salida o ajuste"
        return ctx
