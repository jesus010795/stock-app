from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from employees.models import Department, Employee
from inventory.models import Movement, MovementType
from products.models import Category, Product, Unit
from warehouses.models import Warehouse


class ProductStockTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="stock-tester", password="test1234")
        cls.warehouse = Warehouse.objects.create(code="STK-1", name="Almacén de stock")
        cls.category = Category.objects.create(name="Stock test")
        cls.unit = Unit.objects.create(name="Unidades", abbreviation="u")
        cls.department = Department.objects.create(name="Stock department")
        cls.employee = Employee.objects.create(
            first_name="Test",
            last_name="Stock",
            department=cls.department,
            created_by=cls.user,
        )
        cls.product = Product.objects.create(
            sku="STK-0001",
            name="Producto con stock",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
        )
        cls.empty_product = Product.objects.create(
            sku="STK-0002",
            name="Producto sin stock",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
        )
        Movement.objects.create(
            product=cls.product,
            employee=cls.employee,
            movement_type=MovementType.ENTRY,
            quantity=Decimal("40"),
            reason="Carga inicial",
            created_by=cls.user,
        )
        Movement.objects.create(
            product=cls.product,
            employee=cls.employee,
            movement_type=MovementType.EXIT,
            quantity=Decimal("10"),
            reason="Consumo de prueba",
            created_by=cls.user,
        )

    def test_with_stock_matches_movement_stock(self):
        product = Product.objects.with_stock().get(pk=self.product.pk)

        self.assertEqual(product.stock, Decimal("30"))
        self.assertEqual(
            product.stock, Movement.get_stock_for_product(self.product)
        )

    def test_with_stock_is_zero_without_movements(self):
        product = Product.objects.with_stock().get(pk=self.empty_product.pk)

        self.assertEqual(product.stock, Decimal("0"))
