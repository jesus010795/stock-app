from django.db import models
from django.db.models import Sum, Count
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError


class ProjectStatus(models.TextChoices):
    CREATED = "CREATED", "Creado"
    APPROVED = "APPROVED", "En Curso"
    FINISHED = "FINISHED", "Finalizado"
    CANCELLED = "CANCELLED", "Cancelado"


class ProjectQuerySet(models.QuerySet):
    def with_consumption(self):
        from inventory.models import MovementType
        return self.annotate(
            _product_count=Count("movements__product", distinct=True),
            _total_qty=Sum(
                "movements__quantity",
                filter=models.Q(movements__movement_type=MovementType.EXIT)
            )
        )

    def active(self):
        return self.filter(status__in=[ProjectStatus.CREATED, ProjectStatus.APPROVED])

    def recent(self, limit=5):
        """Últimos proyectos registrados, del más reciente al más antiguo."""
        return self.order_by("-created_at")[:limit]


class ProjectManager(models.Manager):
    def get_queryset(self):
        return ProjectQuerySet(self.model, using=self._db)

    def with_consumption(self):
        return self.get_queryset().with_consumption()

    def active(self):
        return self.get_queryset().active()

    def recent(self, limit=5):
        return self.get_queryset().recent(limit)


class Project(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    client = models.CharField(max_length=200, blank=True, verbose_name="Cliente")
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=ProjectStatus.choices,
        default=ProjectStatus.CREATED
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def product_count(self):
        """Cantidad de productos distintos consumidos en el proyecto.

        Requiere que el queryset haya sido anotado mediante
        Project.objects.with_consumption().
        """
        return getattr(self, "_product_count", 0) or 0

    @property
    def total_consumed(self):
        """Cantidad total de unidades consumidas (salidas) del proyecto.

        Requiere que el queryset haya sido anotado mediante
        Project.objects.with_consumption().
        """
        return getattr(self, "_total_qty", 0) or 0

    objects = ProjectManager()

    class Meta:
        ordering = ['code']
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({
                    'end_date': 'La fecha de cierre no puede ser anterior a la fecha de inicio'
                })
        if self.code and not self.code.strip():
            raise ValidationError({'code': 'El código no puede estar vacío'})

    def delete(self, *args, **kwargs):
        if self.movements.exists():
            raise ProtectedError(
                "No se puede eliminar el proyecto porque tiene movimientos asociados",
                [self],
            )
        super().delete(*args, **kwargs)

    def get_consumed_products(self):
        from inventory.models import Movement, MovementType
        return list(
            Movement.objects.filter(
                project=self,
                movement_type=MovementType.EXIT
            ).values(
                'product__sku',
                'product__name',
                'product__unit__abbreviation'
            ).annotate(
                total_consumed=Sum('quantity')
            ).order_by('product__name')
        )

    def total_movements(self):
        """Cantidad total de movimientos registrados en el proyecto."""
        return self.movements.count()

    def recent_movements(self, limit=10):
        """Últimos movimientos registrados en el proyecto.

        Retorna un queryset optimizado para la ficha del proyecto:
        producto (con unidad), empleado y almacén precargados.
        """
        from inventory.models import Movement

        return (
            Movement.objects.filter(project=self)
            .select_related("product__unit", "employee", "warehouse")
            .order_by("-created_at")[:limit]
        )

    def involved_employees(self, limit=None):
        """Empleados con movimientos registrados en el proyecto.

        Anota, dentro de ESTE proyecto, la cantidad de productos
        distintos (_project_product_count) y las unidades totales de
        salidas (_project_total_qty). Ordenados por su movimiento más
        reciente. Lee los valores con las properties de Employee
        project_product_count / project_total_consumed.
        """
        from employees.models import Employee
        from inventory.models import MovementType

        employees = (
            Employee.objects.filter(movements__project=self)
            .distinct()
            .annotate(
                _project_product_count=models.Count(
                    "movements__product",
                    distinct=True,
                    filter=models.Q(movements__project=self),
                ),
                _project_total_qty=models.Sum(
                    "movements__quantity",
                    filter=models.Q(
                        movements__project=self,
                        movements__movement_type=MovementType.EXIT,
                    ),
                ),
                _last_movement=models.Max("movements__created_at"),
            )
            .select_related("department")
            .order_by("-_last_movement")
        )
        if limit:
            employees = employees[:limit]
        return employees

    def exit_groups_by_employee(self):
        """Historial de salidas del proyecto agrupado por empleado.

        Una sola consulta sobre el índice de `project` (el volumen de
        salidas por proyecto es bajo) y agrupación en Python: los
        empleados se ordenan por su salida más reciente y, dentro de
        cada grupo, las salidas de la más reciente a la más antigua.
        Los movimientos sin empleado (no deberían existir) se agrupan
        con employee=None.
        """
        from collections import OrderedDict

        from inventory.models import Movement, MovementType

        movements = (
            Movement.objects.filter(project=self, movement_type=MovementType.EXIT)
            .select_related("product__unit", "employee__department", "warehouse")
            .order_by("-created_at")
        )

        groups = OrderedDict()
        for movement in movements:
            groups.setdefault(movement.employee, []).append(movement)
        return [
            {"employee": employee, "movements": items}
            for employee, items in groups.items()
        ]
