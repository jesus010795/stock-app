from employees.models import Employee
from projects.models import Project

from .models import AdjustmentType, Movement, MovementType


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
