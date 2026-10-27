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


class LowStockQuerySetTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="low-tester", password="test1234")
        cls.warehouse = Warehouse.objects.create(code="LOW-1", name="Almacén bajo")
        cls.category = Category.objects.create(name="Low stock")
        cls.unit = Unit.objects.create(name="Piezas", abbreviation="p")
        cls.department = Department.objects.create(name="Low stock department")
        cls.employee = Employee.objects.create(
            first_name="Low",
            last_name="Stock",
            department=cls.department,
            created_by=cls.user,
        )
        cls.out_of_stock = Product.objects.create(
            sku="STK-0101",
            name="Producto agotado",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
            minimum_stock=Decimal("10"),
        )
        cls.low_stock = Product.objects.create(
            sku="STK-0102",
            name="Producto con stock bajo",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
            minimum_stock=Decimal("10"),
        )
        cls.healthy = Product.objects.create(
            sku="STK-0103",
            name="Producto con stock sano",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
            minimum_stock=Decimal("10"),
        )
        cls.inactive_out_of_stock = Product.objects.create(
            sku="STK-0104",
            name="Producto inactivo agotado",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
            minimum_stock=Decimal("10"),
            is_active=False,
        )
        cls.without_minimum = Product.objects.create(
            sku="STK-0105",
            name="Producto sin stock mínimo",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
        )
        cls.negative_minimum = Product.objects.create(
            sku="STK-0106",
            name="Producto con stock mínimo negativo",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
            minimum_stock=Decimal("-5"),
        )
        Movement.objects.create(
            product=cls.low_stock,
            employee=cls.employee,
            movement_type=MovementType.ENTRY,
            quantity=Decimal("5"),
            reason="Carga inicial",
            created_by=cls.user,
        )
        Movement.objects.create(
            product=cls.healthy,
            employee=cls.employee,
            movement_type=MovementType.ENTRY,
            quantity=Decimal("50"),
            reason="Carga inicial",
            created_by=cls.user,
        )

    def test_low_stock_includes_only_products_at_or_below_minimum(self):
        skus = {product.sku for product in Product.objects.low_stock()}

        self.assertEqual(
            skus,
            {
                self.out_of_stock.sku,
                self.low_stock.sku,
                self.inactive_out_of_stock.sku,
            },
        )

    def test_low_stock_orders_agotado_first(self):
        skus = [product.sku for product in Product.objects.low_stock()]

        self.assertEqual(
            skus,
            [
                self.out_of_stock.sku,
                self.inactive_out_of_stock.sku,
                self.low_stock.sku,
            ],
        )

    def test_low_stock_matches_the_python_rule(self):
        expected = [
            product
            for product in Product.objects.with_stock()
            if product.is_low_stock
        ]
        expected.sort(
            key=lambda product: (
                product.stock_state != "agotado",
                product.stock_level_pct,
            )
        )

        self.assertEqual(
            [product.sku for product in Product.objects.low_stock()],
            [product.sku for product in expected],
        )

    def test_low_stock_uses_a_single_query(self):
        with self.assertNumQueries(1):
            Product.objects.low_stock()

    def test_low_stock_does_not_trigger_unit_n_plus_one(self):
        with self.assertNumQueries(1):
            abbreviations = [
                product.unit.abbreviation for product in Product.objects.low_stock()
            ]

        self.assertIn("p", abbreviations)
