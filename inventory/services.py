from django.db import transaction

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
