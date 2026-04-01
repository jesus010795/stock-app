from django.db import models
from django.db.models import Sum
from django.core.exceptions import ValidationError


class ProjectStatus(models.TextChoices):
    CREATED = "CREATED", "Creado"
    APPROVED = "APPROVED", "En Curso"
    FINISHED = "FINISHED", "Finalizado"
    CANCELLED = "CANCELLED", "Cancelado"


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

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({
                    'end_date': 'La fecha de cierre no puede ser anterior a la fecha de inicio'
                })

    @property
    def total_consumption(self):
        from inventory.models import Movement, MovementType
        result = Movement.objects.filter(
            project=self,
            movement_type=MovementType.EXIT
        ).aggregate(total=Sum('quantity'))
        return result['total'] or 0

    @property
    def product_count(self):
        return self.movements.values('product').distinct().count()

    def get_consumed_products(self):
        from inventory.models import Movement, MovementType
        return Movement.objects.filter(
            project=self,
            movement_type=MovementType.EXIT
        ).values('product__sku', 'product__name', 'product__unit__abbreviation').annotate(
            total_consumed=Sum('quantity')
        ).order_by('product__name')
