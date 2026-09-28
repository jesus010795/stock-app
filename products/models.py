from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from warehouses.models import Warehouse


class CategoryQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_product_count(self):
        return self.annotate(_product_count=models.Count("products"))


class CategoryManager(models.Manager):
    def get_queryset(self):
        return CategoryQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def with_product_count(self):
        return self.get_queryset().with_product_count()


class Category(models.Model):
    # agregar slug para la categoria
    # En el template de productos, filtrar por categoria y mostrar los productos en cada categoria
    name = models.CharField(
        max_length=100, unique=True, verbose_name="Nombre de la Categoría"
    )
    description = models.TextField(blank=True, verbose_name="Descripción")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CategoryManager()

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.name and not self.name.strip():
            raise ValidationError({"name": "El nombre no puede estar vacío"})

    def delete(self, *args, **kwargs):
        if self.products.exists():
            raise ProtectedError(
                "No se puede eliminar la categoría porque tiene productos asociados",
                [self],
            )
        super().delete(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_category(self):
        return self.select_related("category", "unit", "warehouse")

    def with_stock(self):
        """Anexa el stock calculado a cada producto.

        Mantiene el cálculo en la consulta para que el queryset pueda
        filtrarse y paginarse antes de materializar los productos.
        """
        from django.db.models import Case, DecimalField, F, Sum, Value, When
        from django.db.models.functions import Coalesce
        from inventory.models import AdjustmentType, MovementType

        signed_quantity = Case(
            When(
                movements__movement_type=MovementType.ENTRY,
                then=F("movements__quantity"),
            ),
            When(
                movements__movement_type=MovementType.EXIT,
                then=F("movements__quantity") * -1,
            ),
            When(
                movements__movement_type=MovementType.ADJUSTMENT,
                movements__adjustment_type=AdjustmentType.IN,
                then=F("movements__quantity"),
            ),
            When(
                movements__movement_type=MovementType.ADJUSTMENT,
                movements__adjustment_type=AdjustmentType.OUT,
                then=F("movements__quantity") * -1,
            ),
            default=Value(0),
            output_field=DecimalField(),
        )

        return self.annotate(
            stock=Coalesce(
                Sum(signed_quantity, output_field=DecimalField()),
                Value(0),
                output_field=DecimalField(),
            )
        ).order_by("sku", "name")

    def low_stock(self):
        """Productos en o por debajo de su stock mínimo.

        Materializa with_stock() y filtra en Python para ordenar por
        severidad: agotados primero, luego los más cercanos a quedarse
        sin stock. Retorna una lista.
        """
        products = [product for product in self.with_stock() if product.is_low_stock]
        products.sort(
            key=lambda product: (
                product.stock_state != "agotado",
                product.stock_level_pct,
            )
        )
        return products


class ProductManager(models.Manager):
    def get_queryset(self):
        return ProductQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def with_category(self):
        return self.get_queryset().with_category()

    def with_stock(self):
        return self.get_queryset().with_stock()

    def low_stock(self):
        return self.get_queryset().low_stock()


class Unit(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Unidad de Medida")
    abbreviation = models.CharField(max_length=10, verbose_name="Abreviación")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        verbose_name = "Unidad"
        verbose_name_plural = "Unidades"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

    def clean(self):
        super().clean()
        if self.name and not self.name.strip():
            raise ValidationError({"name": "El nombre no puede estar vacío"})
        if self.abbreviation and not self.abbreviation.strip():
            raise ValidationError(
                {"abbreviation": "La abreviatura no puede estar vacía"}
            )

    def delete(self, *args, **kwargs):
        if self.products.exists():
            raise ProtectedError(
                "No se puede eliminar la unidad porque tiene productos asociados",
                [self],
            )
        super().delete(*args, **kwargs)


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU")
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
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Almacén",
        null=True,
        blank=True,
    )
    description = models.TextField(blank=True, verbose_name="Descripción")
    minimum_stock = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Stock Mínimo",
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_low_stock(self):
        """Indica si el stock está en o por debajo del mínimo.

        Requiere que el atributo `.stock` haya sido anexado previamente
        mediante Product.objects.with_stock(). Si no fue anexado,
        retorna False.
        """
        stock = getattr(self, "stock", None)
        if stock is None:
            return False
        if self.minimum_stock is None or self.minimum_stock < 0:
            return False
        return stock <= self.minimum_stock

    @property
    def stock_state(self):
        """Estado de stock como slug, para presentación y filtros.

        Precedencia: inactivo > agotado > bajo > normal.
        Requiere que `.stock` haya sido anexado con with_stock();
        si no lo fue, se comporta como "normal" (o "inactivo"
        según is_active), igual que is_low_stock.
        """
        if not self.is_active:
            return "inactivo"
        stock = getattr(self, "stock", None)
        if stock is not None and stock <= 0:
            return "agotado"
        if self.is_low_stock:
            return "bajo"
        return "normal"

    @property
    def stock_level_pct(self):
        """Porcentaje (0-100) de la barra de stock, para presentación.

        Heurística: la barra se considera llena al alcanzar 2x el
        stock mínimo.
          - stock <= 0  -> 0
          - sin mínimo  -> 100
          - en otro caso -> min(100, stock / (minimo * 2) * 100)
        Requiere que `.stock` haya sido anexado con with_stock().
        """
        stock = getattr(self, "stock", None)
        if stock is None or stock <= 0:
            return 0
        minimum = self.minimum_stock
        if minimum is None or minimum <= 0:
            return 100
        return min(100, round(stock / (minimum * 2) * 100))

    objects = ProductManager()

    class Meta:
        ordering = ["sku", "name"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["category"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def clean(self):
        super().clean()
        if not self.sku or not self.sku.strip():
            raise ValidationError({"sku": "El SKU es obligatorio"})
        if self.sku:
            self.sku = self.sku.strip().upper()
        if not self.name or not self.name.strip():
            raise ValidationError({"name": "El nombre es obligatorio"})
        if self.minimum_stock is not None and self.minimum_stock < 0:
            raise ValidationError(
                {"minimum_stock": "El stock mínimo no puede ser negativo"}
            )
        if not self.warehouse:
            raise ValidationError({"warehouse": "El almacén es obligatorio"})

    def delete(self, *args, **kwargs):
        if self.movements.exists():
            raise ProtectedError(
                "No se puede eliminar el producto porque tiene movimientos asociados",
                [self],
            )
        super().delete(*args, **kwargs)
