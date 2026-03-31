from django.db import models
from django.db.models import Sum


class Project(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

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
