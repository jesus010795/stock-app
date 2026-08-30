from django.db import models
from django.contrib.auth.models import User


class DepartmentQuerySet(models.QuerySet):
    def with_employee_count(self):
        """Anota la cantidad de empleados asociados al departamento."""
        return self.annotate(_employee_count=models.Count("employees"))


class DepartmentManager(models.Manager):
    def get_queryset(self):
        return DepartmentQuerySet(self.model, using=self._db)

    def with_employee_count(self):
        return self.get_queryset().with_employee_count()


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Departamento")
    description = models.TextField(blank=True, verbose_name="Descripción")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def employee_count(self):
        """Cantidad de empleados en el departamento.

        Requiere que el queryset haya sido anotado mediante
        Department.objects.with_employee_count().
        """
        return getattr(self, "_employee_count", 0) or 0

    objects = DepartmentManager()

    class Meta:
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"
        ordering = ["name"]

    def __str__(self):
        return self.name


class EmployeeQuerySet(models.QuerySet):
    def with_consumption(self):
        """Anota la cantidad de productos distintos y el total consumido.

        El consumo se calcula a partir de los movimientos de tipo EXIT
        asociados a cada empleado.
        """
        from inventory.models import MovementType

        return self.annotate(
            _product_count=models.Count("movements__product", distinct=True),
            _total_qty=models.Sum(
                "movements__quantity",
                filter=models.Q(movements__movement_type=MovementType.EXIT),
            ),
        )


class EmployeeManager(models.Manager):
    def get_queryset(self):
        return EmployeeQuerySet(self.model, using=self._db)

    def with_consumption(self):
        return self.get_queryset().with_consumption()


class Employee(models.Model):
    first_name = models.CharField(max_length=100, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, verbose_name="Apellido")
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name="Departamento"
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_employees",
        verbose_name="Creado por (Admin)"
    )

    @property
    def product_count(self):
        """Cantidad de productos distintos consumidos por el empleado.

        Requiere que el queryset haya sido anotado mediante
        Employee.objects.with_consumption().
        """
        return getattr(self, "_product_count", 0) or 0

    @property
    def total_consumed(self):
        """Cantidad total de unidades consumidas (salidas) por el empleado.

        Requiere que el queryset haya sido anotado mediante
        Employee.objects.with_consumption().
        """
        return getattr(self, "_total_qty", 0) or 0

    objects = EmployeeManager()

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.last_name}, {self.first_name} ({self.department.name})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
