from django.db import transaction
from products.models import Product

from .models import Movement


def register_movement(
    *,
    product,
    employee,
    movement_type,
    quantity,
    project=None,
    reason="",
    adjustment_type=None,
    created_by=None,
):
    """Registra un movimiento de inventario de forma transaccional.

    Caso de uso completo de escritura: coordina la creación del
    movimiento dentro de una transacción todo-o-nada. Las reglas de
    coherencia de la fila y la validación de stock viven en
    Movement.clean()/save() (fuente única, también protege al admin).
    """
    with transaction.atomic():
        # Bloquea la fila del producto hasta el COMMIT: serializa a los
        # escritores de un mismo producto y hace que la validación de
        # stock de save() lea el estado ya actualizado (evita la carrera
        # de lectura-validación-escritura en PostgreSQL). En SQLite
        # select_for_update() es un no-op y se pierde la protección.
        product = Product.objects.select_for_update().get(pk=product.pk)
        movement = Movement(
            product=product,
            employee=employee,
            movement_type=movement_type,
            quantity=quantity,
            project=project,
            reason=reason,
            adjustment_type=adjustment_type,
            created_by=created_by,
        )
        movement.save()
        return movement
