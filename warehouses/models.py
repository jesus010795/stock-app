from django.db import models
from django.core.exceptions import ValidationError


class WarehouseType(models.TextChoices):
    GENERAL = "GENERAL", "General"
    ELECTRICAL = "ELECTRICAL", "Eléctricos"
    PNEUMATIC = "PNEUMATIC", "Neumáticos"
    CONTROLS = "CONTROLS", "Controles"
    COILS = "COILS", "Bobinas"
    RAW_MATERIAL = "RAW_MATERIAL", "Materia Prima"
    FINISHED_GOODS = "FINISHED_GOODS", "Producto Terminado"


class WarehouseQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class WarehouseManager(models.Manager):
    def get_queryset(self):
        return WarehouseQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def get_or_create_general(self):
        return self.get_or_create(
            code="GENERAL",
            defaults={
                "name": "Almacén General",
                "warehouse_type": WarehouseType.GENERAL,
                "is_active": True,
            }
        )


class Warehouse(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    warehouse_type = models.CharField(
        max_length=20,
        choices=WarehouseType.choices,
        default=WarehouseType.GENERAL
    )
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = WarehouseManager()

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["warehouse_type"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        super().clean()
        if self.code and not self.code.strip():
            raise ValidationError({"code": "El código no puede estar vacío"})

    def delete(self, *args, **kwargs):
        if self.products.exists():
            raise models.ProtectedError(
                "No se puede eliminar el warehouse porque tiene productos asociados",
                [self],
            )
        super().delete(*args, **kwargs)