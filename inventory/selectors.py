from django.db.models import Q

from employees.models import Employee
from products.models import Product
from projects.models import Project

from .models import AdjustmentType, Movement, MovementType, stock_expression


def recent_activity(limit=5):
    """Feed mixto de actividad reciente para el dashboard.

    Combina movimientos, proyectos creados y empleados agregados,
    ordenados del más reciente al más antiguo. Cada evento es un
    diccionario {icon, fa, actor, action, target, created_at} con la
    redacción resuelta en el selector, para que la plantilla solo pinte.
    """
    events = []

    for movement in Movement.objects.recent(limit=limit):
        if movement.movement_type == MovementType.EXIT:
            icon, fa, action = "danger", "fa-arrow-up", "registró una salida de"
        elif movement.movement_type == MovementType.ENTRY:
            icon, fa, action = "success", "fa-arrow-down", "registró una entrada de"
        elif movement.adjustment_type == AdjustmentType.IN:
            icon, fa, action = (
                "info",
                "fa-arrow-up",
                "registró un ajuste de aumento de",
            )
        else:
            icon, fa, action = (
                "info",
                "fa-arrow-down",
                "registró un ajuste de disminución de",
            )
        events.append(
            {
                "icon": icon,
                "fa": fa,
                "actor": (
                    movement.employee.full_name if movement.employee else "Sistema"
                ),
                "action": action,
                "target": movement.product.name,
                "created_at": movement.created_at,
            }
        )

    for project in Project.objects.recent(limit=limit):
        events.append(
            {
                "icon": "purple",
                "fa": "fa-project-diagram",
                "actor": project.name,
                "action": "fue creado en el sistema",
                "target": None,
                "created_at": project.created_at,
            }
        )

    for employee in (
        Employee.objects.order_by("-created_at").select_related("department")[:limit]
    ):
        events.append(
            {
                "icon": "info",
                "fa": "fa-user-plus",
                "actor": employee.full_name,
                "action": "fue agregado al área de",
                "target": employee.department.name,
                "created_at": employee.created_at,
            }
        )

    events.sort(key=lambda event: event["created_at"], reverse=True)
    return events[:limit]


def product_label(product):
    """Etiqueta de cada opción del autocompletado de productos.

    Formato: `SKU - nombre · stock`. La consume el endpoint de
    autocompletado product_search y exige que el queryset haya
    anexado `.stock` (stock_expression anotada).
    """
    stock = getattr(product, "stock", None)
    if stock is None:
        return str(product)
    return f"{product} · stock: {stock:g}"


def search_products(query, limit=10):
    """Productos activos cuyo SKU o nombre contiene `query`, con stock.

    Dos consultas: la primera trae solo los `limit` pks que coinciden
    (ordenados por sku, name), la segunda anota el stock únicamente
    sobre esos pks. La agregación de movimientos queda acotada a las
    filas que se van a mostrar, no a todos los coincidentes.
    """
    pks = list(
        Product.objects.active()
        .filter(Q(sku__icontains=query) | Q(name__icontains=query))
        .order_by("sku", "name")
        .values_list("pk", flat=True)[:limit]
    )
    if not pks:
        return []
    products = Product.objects.filter(pk__in=pks).annotate(
        stock=stock_expression("movements__")
    )
    by_pk = {product.pk: product for product in products}
    return [by_pk[pk] for pk in pks if pk in by_pk]


def product_for_autocomplete(pk):
    """Producto activo con stock anexado, por pk.

    Sirve para restaurar la etiqueta del campo prefijado (?producto=)
    o al re-renderizar el form con errores.
    """
    return (
        Product.objects.active()
        .filter(pk=pk)
        .annotate(stock=stock_expression("movements__"))
        .first()
    )


def search_employees(query, limit=10):
    """Empleados activos cuyo nombre o apellido contiene `query`.

    select_related("department") porque Employee.__str__ toca el nombre
    del departamento: sin el join habría N+1 por opción.
    """
    return list(
        Employee.objects.filter(is_active=True)
        .filter(Q(first_name__icontains=query) | Q(last_name__icontains=query))
        .select_related("department")[:limit]
    )


def employee_for_autocomplete(pk):
    """Empleado activo por pk, para restaurar la etiqueta del campo."""
    return (
        Employee.objects.filter(is_active=True, pk=pk)
        .select_related("department")
        .first()
    )


def search_projects(query, limit=10):
    """Proyectos activos (CREATED/APPROVED) cuyo código o nombre contiene `query`."""
    return list(
        Project.objects.active()
        .filter(Q(code__icontains=query) | Q(name__icontains=query))
        .order_by("code", "name")[:limit]
    )


def project_for_autocomplete(pk):
    """Proyecto activo por pk, para restaurar la etiqueta del campo."""
    return Project.objects.active().filter(pk=pk).first()
