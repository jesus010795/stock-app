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


class ProjectManager(models.Manager):
    def get_queryset(self):
        return ProjectQuerySet(self.model, using=self._db)

    def with_consumption(self):
        return self.get_queryset().with_consumption()

    def active(self):
        return self.get_queryset().active()


class Project(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
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
            models.Index(fields=["code"]),
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
