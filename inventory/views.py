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
from .selectors import (
    employee_for_autocomplete,
    product_for_autocomplete,
    product_label,
    project_for_autocomplete,
    recent_activity,
    search_employees,
    search_products,
    search_projects,
)
from .services import register_movement


# Create your views here.
LOW_STOCK_DISPLAY_LIMIT = 6
STAFF_REQUIRED_MESSAGE = (
    "Tu cuenta no tiene permisos para registrar movimientos."
)
AUTOCOMPLETE_MIN_LENGTH = 2
AUTOCOMPLETE_LIMIT = 10


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
    """Fila JSON de un producto para el autocompletado del form.

    El stock se serializa sin ceros redundantes para que SQLite y
    PostgreSQL produzcan la misma cadena (Decimal("100.00") y
    Decimal("100") dan "100" en ambos motores).
    """
    stock = getattr(product, "stock", None)
    stock_str = None
    if stock is not None:
        # Solo se recortan ceros tras el punto decimal: "100.00" → "100",
        # "100.50" → "100.5" y un entero como "100" queda igual.
        stock_str = format(stock, "f")
        if "." in stock_str:
            stock_str = stock_str.rstrip("0").rstrip(".")
    return {
        "id": product.pk,
        "label": product_label(product),
        "stock": stock_str,
    }


@require_GET
def product_search(request):
    """Autocompletado en tiempo real del campo producto de /movimientos/nuevo/.

    Endpoint JSON de la app: alimenta el buscador del formulario, no es
    una API pública. Acceso exclusivo de staff; ante sesión caducada o
    usuario sin permisos responde 403 en JSON (es un fetch del navegador,
    no una navegación: redirigir al login no sirve).

    La vista solo hace auth, parseo de `q`/`id` y la forma del JSON; la
    consulta y la etiqueta viven en inventory/selectors.py.

    - `?q=<texto>`: productos activos cuyo SKU o nombre contiene el
      texto (mínimo AUTOCOMPLETE_MIN_LENGTH caracteres, máximo
      AUTOCOMPLETE_LIMIT resultados). search_products anota el stock
      solo sobre los resultados, no sobre todos los coincidentes.
    - `?id=<pk>`: un único producto activo, para restaurar la etiqueta
      del campo prefijado (?producto=) o al re-renderizar con errores.
    """
    if not request.user.is_staff:
        return JsonResponse({"error": "No autorizado"}, status=403)

    product_id = request.GET.get("id")
    if product_id and product_id.isdigit():
        product = product_for_autocomplete(int(product_id))
        results = [_product_payload(product)] if product else []
        return JsonResponse({"results": results})

    query = (request.GET.get("q") or "").strip()
    if len(query) < AUTOCOMPLETE_MIN_LENGTH:
        return JsonResponse({"results": []})

    results = [
        _product_payload(product)
        for product in search_products(query, AUTOCOMPLETE_LIMIT)
    ]
    return JsonResponse({"results": results})


def _employee_payload(employee):
    """Fila JSON de un empleado para el autocompletado del form."""
    return {"id": employee.pk, "label": str(employee)}


@require_GET
def employee_search(request):
    """Autocompletado en tiempo real del campo empleado de /movimientos/nuevo/.

    Mismo contrato que product_search: staff-only, `?q=` busca empleados
    activos por nombre o apellido (mínimo AUTOCOMPLETE_MIN_LENGTH, tope
    AUTOCOMPLETE_LIMIT) y `?id=` devuelve un empleado activo para
    restaurar la etiqueta del campo.
    """
    if not request.user.is_staff:
        return JsonResponse({"error": "No autorizado"}, status=403)

    employee_id = request.GET.get("id")
    if employee_id and employee_id.isdigit():
        employee = employee_for_autocomplete(int(employee_id))
        results = [_employee_payload(employee)] if employee else []
        return JsonResponse({"results": results})

    query = (request.GET.get("q") or "").strip()
    if len(query) < AUTOCOMPLETE_MIN_LENGTH:
        return JsonResponse({"results": []})

    results = [
        _employee_payload(employee)
        for employee in search_employees(query, AUTOCOMPLETE_LIMIT)
    ]
    return JsonResponse({"results": results})


def _project_payload(project):
    """Fila JSON de un proyecto para el autocompletado del form."""
    return {"id": project.pk, "label": str(project)}


@require_GET
def project_search(request):
    """Autocompletado en tiempo real del campo proyecto de /movimientos/nuevo/.

    Mismo contrato que product_search: staff-only, `?q=` busca proyectos
    activos (CREATED/APPROVED) por código o nombre (mínimo
    AUTOCOMPLETE_MIN_LENGTH, tope AUTOCOMPLETE_LIMIT) y `?id=` devuelve
    un proyecto activo para restaurar la etiqueta del campo.
    """
    if not request.user.is_staff:
        return JsonResponse({"error": "No autorizado"}, status=403)

    project_id = request.GET.get("id")
    if project_id and project_id.isdigit():
        project = project_for_autocomplete(int(project_id))
        results = [_project_payload(project)] if project else []
        return JsonResponse({"results": results})

    query = (request.GET.get("q") or "").strip()
    if len(query) < AUTOCOMPLETE_MIN_LENGTH:
        return JsonResponse({"results": []})

    results = [
        _project_payload(project)
        for project in search_projects(query, AUTOCOMPLETE_LIMIT)
    ]
    return JsonResponse({"results": results})
