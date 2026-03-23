from django.db import models


class Category(models.Model):
    name = models.CharField(
        max_length=100, unique=True, verbose_name="Nombre de la Categoría"
    )
    description = models.TextField(blank=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Unit(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Unidad de Medida")
    abbreviation = models.CharField(max_length=10, verbose_name="Abreviación")

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

    class Meta:
        verbose_name = "Unidad"
        verbose_name_plural = "Unidades"
        ordering = ["name"]


class Product(models.Model):
    sku = models.CharField(
        max_length=50, unique=True, blank=True, null=True, verbose_name="SKU"
    )
    name = models.CharField(max_length=200, verbose_name="Nombre del Producto")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Categoría",
    )
    unit = models.ForeignKey(
        Unit, on_delete=models.PROTECT, related_name="products", verbose_name="Unidad"
    )
    description = models.TextField(blank=True, verbose_name="Descripción")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sku", "name"]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    @property
    def current_stock(self):
        """
        Calcula el stock actual sumando todos los movimientos.
        Se implementará cuando exista el modelo Movement.
        """
        return 0
