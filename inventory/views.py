from django.shortcuts import render
from django.views.generic import CreateView, TemplateView
from products.models import Product
from .models import Movement
from .forms import MovementForm
from django.urls import reverse_lazy
from django.contrib import messages


# Create your views here.
class HomeView(TemplateView):
    template_name = "inventory/home.html"


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
