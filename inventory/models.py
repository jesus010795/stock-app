from django.db import models
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError
from products.models import Product
from projects.models import Project


class MovementType(models.TextChoices):
    ENTRY = "ENTRY", "Entrada"
    EXIT = "EXIT", "Salida"
    ADJUSTMENT = "AJUST", "Ajuste"


class AdjustmentType(models.TextChoices):
    IN = "IN", "Aumento"
    OUT = "OUT", "Disminución"


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

    def clean(self):
        super().clean()

        if not self.quantity or self.quantity <= 0:
            raise ValidationError({"quantity": "La cantidad debe ser mayor a 0"})

        if self.movement_type == MovementType.ADJUSTMENT:
            if not self.adjustment_type:
                raise ValidationError(
                    {"adjustment_type": "Debe seleccionar tipo de ajuste"}
                )
            if not self.reason:
                raise ValidationError({"reason": "Debe ingresar el motivo del ajuste"})
        else:
            if self.adjustment_type:
                raise ValidationError({"adjustment_type": "Solo aplica para ajustes"})

        if self.movement_type == MovementType.EXIT:
            if not self.project and not self.reason:
                raise ValidationError(
                    {"reason": "Debe indicar proyecto o motivo de la salida"}
                )

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
        return f"{self.product.sku} - {self.movement_type} - {self.quantity}"
