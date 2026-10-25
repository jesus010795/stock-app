from django.db import models
from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.core.exceptions import ValidationError
from products.models import Product
from projects.models import Project, ProjectStatus
from warehouses.models import Warehouse
from employees.models import Employee


class MovementType(models.TextChoices):
    ENTRY = "ENTRY", "Entrada"
    EXIT = "EXIT", "Salida"
    ADJUSTMENT = "AJUST", "Ajuste"


class AdjustmentType(models.TextChoices):
    IN = "IN", "Aumento"
    OUT = "OUT", "Disminución"


class MovementQuerySet(models.QuerySet):
    def for_product(self, product):
        return self.filter(product=product)

    def for_project(self, project):
        return self.filter(project=project)

    def entries(self):
        return self.filter(movement_type=MovementType.ENTRY)

    def exits(self):
        return self.filter(movement_type=MovementType.EXIT)

    def adjustments(self):
        return self.filter(movement_type=MovementType.ADJUSTMENT)

    def recent(self, limit=10):
        """Últimos movimientos registrados, del más reciente al más antiguo.

        Precarga producto (con unidad), empleado, proyecto y almacén
        para las tarjetas del dashboard y las fichas de detalle.
        """
        return self.select_related(
            "product__unit", "employee", "project", "warehouse"
        ).order_by("-created_at")[:limit]

    def with_product_stock(self):
        return self.annotate(
            _stock=Coalesce(
                Sum(
                    Case(
                        When(movement_type=MovementType.ENTRY, then=F("quantity")),
                        When(movement_type=MovementType.EXIT, then=F("quantity") * -1),
                        When(
                            movement_type=MovementType.ADJUSTMENT,
                            adjustment_type=AdjustmentType.IN,
                            then=F("quantity"),
                        ),
                        When(
                            movement_type=MovementType.ADJUSTMENT,
                            adjustment_type=AdjustmentType.OUT,
                            then=F("quantity") * -1,
                        ),
                        default=Value(0),
                        output_field=DecimalField(),
                    )
                ),
                Value(0),
                output_field=DecimalField(),
            )
        )

    def get_products_with_stock(self):
        return (
            self.values("product")
            .annotate(
                _stock=Coalesce(
                    Sum(
                        Case(
                            When(movement_type=MovementType.ENTRY, then=F("quantity")),
                            When(
                                movement_type=MovementType.EXIT, then=F("quantity") * -1
                            ),
                            When(
                                movement_type=MovementType.ADJUSTMENT,
                                adjustment_type=AdjustmentType.IN,
                                then=F("quantity"),
                            ),
                            When(
                                movement_type=MovementType.ADJUSTMENT,
                                adjustment_type=AdjustmentType.OUT,
                                then=F("quantity") * -1,
                            ),
                            default=Value(0),
                            output_field=DecimalField(),
                        )
                    ),
                    Value(0),
                    output_field=DecimalField(),
                )
            )
            .values("product__id", "product__sku", "product__name", "_stock")
        )
class Movement(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="movements"
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="Empleado",
    )
    movement_type = models.CharField(max_length=10, choices=MovementType.choices)
    adjustment_type = models.CharField(
        max_length=3, choices=AdjustmentType.choices, blank=True, null=True
    )
    quantity = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Cantidad"
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, related_name="movements"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["project"]),
            models.Index(fields=["movement_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["product", "movement_type"]),
        ]

    objects = MovementQuerySet.as_manager()

    def clean(self):
        super().clean()

        if not self.quantity or self.quantity <= 0:
            raise ValidationError({"quantity": "La cantidad debe ser mayor a 0"})

        if not self.warehouse and self.product_id:
            self.warehouse = self.product.warehouse

        if not self.employee:
            raise ValidationError({"employee": "Debe seleccionar un empleado"})

        if self.movement_type == MovementType.EXIT:
            if not self.project and not self.reason:
                raise ValidationError(
                    {"reason": "Debe indicar proyecto o motivo de la salida"}
                )
            if self.project and self.project.status != ProjectStatus.APPROVED:
                raise ValidationError(
                    {
                        "project": "Solo se puede sacar material para proyectos en curso (Aprobados)"
                    }
                )

        if self.movement_type == MovementType.ENTRY:
            if not self.project and not self.reason:
                raise ValidationError(
                    {"reason": "Debe indicar proyecto o motivo de la entrada"}
                )

        if self.movement_type == MovementType.ADJUSTMENT:
            if not self.adjustment_type:
                raise ValidationError(
                    {"adjustment_type": "Debe seleccionar tipo de ajuste"}
                )
            if not self.reason:
                raise ValidationError({"reason": "Debe ingresar el motivo del ajuste"})
        else:
            if self.adjustment_type:
                self.adjustment_type = None
                # raise ValidationError({"adjustment_type": "Solo aplica para ajustes"})

    def save(self, *args, **kwargs):
        self.full_clean()

        if self.movement_type in [MovementType.EXIT, MovementType.ADJUSTMENT]:
            current_stock = self.get_stock_for_product(self.product)
            quantity_to_deduct = (
                self.quantity
                if self.movement_type == MovementType.EXIT
                else (
                    self.quantity if self.adjustment_type == AdjustmentType.OUT else 0
                )
            )
            if current_stock - quantity_to_deduct < 0:
                raise ValidationError(
                    {"quantity": f"Stock insuficiente. Stock actual: {current_stock}"}
                )

        super().save(*args, **kwargs)

    @classmethod
    def get_stock_for_product(cls, product):
        result = cls.objects.filter(product=product).aggregate(
            entries=Sum(
                "quantity",
                output_field=models.DecimalField(),
                filter=Q(movement_type=MovementType.ENTRY),
            ),
            exits=Sum(
                "quantity",
                output_field=models.DecimalField(),
                filter=Q(movement_type=MovementType.EXIT),
            ),
            adjustments_in=Sum(
                "quantity",
                output_field=models.DecimalField(),
                filter=Q(
                    movement_type=MovementType.ADJUSTMENT,
                    adjustment_type=AdjustmentType.IN,
                ),
            ),
            adjustments_out=Sum(
                "quantity",
                output_field=models.DecimalField(),
                filter=Q(
                    movement_type=MovementType.ADJUSTMENT,
                    adjustment_type=AdjustmentType.OUT,
                ),
            ),
        )
        entries = result["entries"] or 0
        exits = result["exits"] or 0
        adjustments_in = result["adjustments_in"] or 0
        adjustments_out = result["adjustments_out"] or 0
        return entries + adjustments_in - exits - adjustments_out

    @classmethod
    def get_project_consumption(cls, project):
        result = cls.objects.filter(
            project=project, movement_type=MovementType.EXIT
        ).aggregate(total=Sum("quantity"))
        return result["total"] or 0

    @classmethod
    def get_product_consumption_in_project(cls, product, project):
        result = cls.objects.filter(
            product=product, project=project, movement_type=MovementType.EXIT
        ).aggregate(total=Sum("quantity"))
        return result["total"] or 0

    def __str__(self):
        return f"{self.product.sku} - {self.movement_type} - {self.signed_quantity}"

    @property
    def signed_quantity(self):
        if self.movement_type == MovementType.ENTRY:
            return self.quantity
        elif self.movement_type == MovementType.EXIT:
            return -self.quantity
        elif self.movement_type == MovementType.ADJUSTMENT:
            if self.adjustment_type == AdjustmentType.IN:
                return self.quantity
            return -self.quantity
        return self.quantity

    @classmethod
    def get_recent_activity(cls, limit=5):
        """Feed mixto de actividad reciente para el dashboard.

        Combina movimientos, proyectos creados y empleados agregados,
        ordenados del más reciente al más antiguo. Cada evento es un
        diccionario {icon, fa, actor, action, target, created_at} con la
        redacción resuelta en el modelo, para que la plantilla solo pinte.
        """
        events = []

        for movement in cls.objects.recent(limit=limit):
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

        for employee in Employee.objects.order_by("-created_at")[:limit]:
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
