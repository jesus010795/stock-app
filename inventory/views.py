from django.shortcuts import render
from django.views.generic import CreateView, TemplateView
from products.models import Product
from projects.models import Project
from .models import Movement
from .forms import MovementForm
from .selectors import recent_activity
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect


# Create your views here.
LOW_STOCK_DISPLAY_LIMIT = 6


class HomeView(TemplateView):
    template_name = "inventory/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        low_stock = Product.objects.low_stock()
        context["low_stock_count"] = low_stock.count()
        context["low_stock_products"] = list(low_stock[:LOW_STOCK_DISPLAY_LIMIT])
        context["recent_movements"] = Movement.objects.recent(limit=10)
        context["recent_projects"] = Project.objects.recent(limit=5)
        context["recent_activity"] = recent_activity(limit=5)
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
        if product_id and str(product_id).isdigit():
            if Product.objects.filter(pk=product_id).exists():
                initial["product"] = product_id
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        try:
            self.object = form.save()
        except ValidationError as e:
            if hasattr(e, "message_dict"):
                for field, errors in e.message_dict.items():
                    form.add_error(field if field in form.fields else None, errors)
            else:
                form.add_error(None, e.messages)
            return self.form_invalid(form)
        messages.success(self.request, "Movimiento registrado correctamente")
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb_title"] = "Nuevo Movimiento"
        ctx["breadcrumb_subtitle"] = "Registrar entrada, salida o ajuste"
        return ctx
