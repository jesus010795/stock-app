from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DetailView, ListView, TemplateView
from products.models import Product
from projects.models import Project

from .forms import MovementFilterForm, MovementForm
from .models import Movement
from .selectors import recent_activity
from .services import register_movement


# Create your views here.
LOW_STOCK_DISPLAY_LIMIT = 6
STAFF_REQUIRED_MESSAGE = (
    "Tu cuenta no tiene permisos para registrar movimientos."
)
PRODUCT_SEARCH_MIN_LENGTH = 2
PRODUCT_SEARCH_LIMIT = 10


class StaffRequiredMixin(LoginRequiredMixin):
    """Sesión y is_staff. Anónimo va al login; no-staff vuelve al dashboard."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_staff:
            messages.error(request, STAFF_REQUIRED_MESSAGE)
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)


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


class MovementListView(ListView):
    model = Movement
    template_name = "inventory/movimiento_list.html"
    context_object_name = "movements"
    paginate_by = 20

    def get_queryset(self):
        queryset = Movement.objects.select_related(
            "product__unit", "employee", "project", "warehouse"
        )
        form = MovementFilterForm(self.request.GET)
        if form.is_valid():
            movement_type = form.cleaned_data["movement_type"]
            if movement_type:
                queryset = queryset.filter(movement_type=movement_type)

            query = form.cleaned_data["q"]
            if query:
                queryset = queryset.filter(
                    Q(product__sku__icontains=query)
                    | Q(product__name__icontains=query)
                )

            # Límites de fecha como datetimes (no __date) para evitar
            # la dependencia de la zona horaria de la conexión.
            desde = form.cleaned_data["desde"]
            if desde:
                queryset = queryset.filter(
                    created_at__gte=datetime.combine(desde, time.min)
                )
            hasta = form.cleaned_data["hasta"]
            if hasta:
                queryset = queryset.filter(
                    created_at__lt=datetime.combine(hasta, time.min)
                    + timedelta(days=1)
                )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = MovementFilterForm(self.request.GET)
        context["breadcrumb_title"] = "Movimientos"
        context["breadcrumb_subtitle"] = "Historial de entradas, salidas y ajustes"
        return context


class MovementDetailView(DetailView):
    model = Movement
    template_name = "inventory/movimiento_detail.html"
    context_object_name = "movement"

    def get_queryset(self):
        return Movement.objects.select_related(
            "product__unit", "employee__department", "project", "warehouse", "created_by"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumb_title"] = "Movimientos"
        context["breadcrumb_subtitle"] = "Detalle del movimiento"
        return context


class MovementCreateView(StaffRequiredMixin, CreateView):
    model = Movement
    form_class = MovementForm
    template_name = "inventory/movimiento_form.html"
    success_url = reverse_lazy("inventory:historial")

    def get_initial(self):
        initial = super().get_initial()
        product_id = self.request.GET.get("producto")
        if product_id and str(product_id).isdigit():
            # Solo activos: el autocompletado y la validación del form
            # usan el mismo queryset.
            if Product.objects.active().filter(pk=product_id).exists():
                initial["product"] = product_id
        return initial

    def form_valid(self, form):
        try:
            self.object = register_movement(
                product=form.cleaned_data["product"],
                employee=form.cleaned_data["employee"],
                movement_type=form.cleaned_data["movement_type"],
                quantity=form.cleaned_data["quantity"],
                project=form.cleaned_data.get("project"),
                reason=form.cleaned_data.get("reason") or "",
                adjustment_type=form.cleaned_data.get("adjustment_type"),
                created_by=self.request.user,
            )
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


def _product_payload(product):
    """Fila JSON de un producto para el autocompletado del form."""
    stock = getattr(product, "stock", None)
    return {
        "id": product.pk,
        "label": MovementForm.product_option_label(product),
        "stock": str(stock) if stock is not None else None,
    }


@require_GET
def buscar_productos(request):
    """Autocompletado en tiempo real del campo producto de /movimientos/nuevo/.

    Primer (y único) endpoint JSON de la app: alimenta el buscador del
    formulario, no es una API pública. Acceso exclusivo de staff; ante
    sesión caducada o usuario sin permisos responde 403 en JSON (es un
    fetch del navegador, no una navegación: redirigir al login no sirve).

    - `?q=<texto>`: productos activos cuyo SKU o nombre contiene el
      texto (mínimo PRODUCT_SEARCH_MIN_LENGTH caracteres, máximo
      PRODUCT_SEARCH_LIMIT resultados).
    - `?id=<pk>`: un único producto activo, para restaurar la etiqueta
      del campo prefijado (?producto=) o al re-renderizar con errores.
    """
    if not request.user.is_staff:
        return JsonResponse({"error": "No autorizado"}, status=403)

    product_id = request.GET.get("id")
    if product_id and product_id.isdigit():
        product = (
            Product.objects.active().with_stock().filter(pk=product_id).first()
        )
        results = [_product_payload(product)] if product else []
        return JsonResponse({"results": results})

    query = (request.GET.get("q") or "").strip()
    if len(query) < PRODUCT_SEARCH_MIN_LENGTH:
        return JsonResponse({"results": []})

    queryset = (
        Product.objects.active()
        .with_stock()
        .filter(Q(sku__icontains=query) | Q(name__icontains=query))
    )
    results = [
        _product_payload(product)
        for product in queryset[:PRODUCT_SEARCH_LIMIT]
    ]
    return JsonResponse({"results": results})
