from datetime import timedelta
from decimal import Decimal

import threading

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from django.urls import reverse

from employees.models import Department, Employee
from inventory.forms import MovementForm
from inventory.models import AdjustmentType, Movement, MovementType
from inventory.selectors import recent_activity
from inventory.services import register_movement
from inventory.views import LOW_STOCK_DISPLAY_LIMIT
from products.models import Category, Product, Unit
from projects.models import Project, ProjectStatus
from warehouses.models import Warehouse


class MovementFormTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="tester", password="test1234")
        cls.warehouse = Warehouse.objects.create(code="ALM-1", name="Almacén Uno")
        cls.category = Category.objects.create(name="Cables")
        cls.unit = Unit.objects.create(name="Metros", abbreviation="m")
        cls.product = Product.objects.create(
            sku="TST-0001",
            name="Cable de prueba",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
            minimum_stock=Decimal("10"),
        )
        cls.inactive_product = Product.objects.create(
            sku="TST-0002",
            name="Producto inactivo",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
            is_active=False,
        )
        cls.department = Department.objects.create(name="Mantenimiento")
        cls.employee = Employee.objects.create(
            first_name="Ana",
            last_name="Pérez",
            department=cls.department,
            created_by=cls.user,
        )
        cls.inactive_employee = Employee.objects.create(
            first_name="Luis",
            last_name="López",
            department=cls.department,
            is_active=False,
            created_by=cls.user,
        )
        cls.project_approved = Project.objects.create(
            code="PRJ-001",
            name="Proyecto aprobado",
            status=ProjectStatus.APPROVED,
        )
        cls.project_created = Project.objects.create(
            code="PRJ-002",
            name="Proyecto creado",
            status=ProjectStatus.CREATED,
        )
        cls.project_finished = Project.objects.create(
            code="PRJ-003",
            name="Proyecto finalizado",
            status=ProjectStatus.FINISHED,
        )
        Movement.objects.create(
            product=cls.product,
            employee=cls.employee,
            movement_type=MovementType.ENTRY,
            quantity=Decimal("100"),
            reason="Carga inicial",
            created_by=cls.user,
        )

    def form_data(self, **overrides):
        data = {
            "product": self.product.pk,
            "movement_type": MovementType.EXIT.value,
            "adjustment_type": "",
            "quantity": "5",
            "employee": self.employee.pk,
            "project": self.project_approved.pk,
            "reason": "",
        }
        data.update(overrides)
        return data

    def url(self):
        return reverse("inventory:nuevo")


class MovementFormPresentationTest(MovementFormTestBase):
    def test_labels_in_spanish(self):
        form = MovementForm()
        casos = {
            "product": "Producto",
            "movement_type": "Tipo de movimiento",
            "adjustment_type": "Tipo de ajuste",
            "employee": "Empleado",
            "project": "Proyecto",
            "reason": "Motivo",
        }
        for campo, esperado in casos.items():
            with self.subTest(campo=campo):
                self.assertEqual(form[campo].label, esperado)

    def test_widgets_use_design_system_classes(self):
        form = MovementForm()
        self.assertIn('class="select"', str(form["product"]))
        self.assertIn('class="input"', str(form["quantity"]))
        self.assertIn('step="0.01"', str(form["quantity"]))
        self.assertIn('class="textarea"', str(form["reason"]))

    def test_help_texts_explain_conditional_rules(self):
        form = MovementForm()
        self.assertIn("Solo aplica para ajustes", form.fields["adjustment_type"].help_text)
        self.assertIn("aprobados", form.fields["project"].help_text)
        self.assertIn("salidas sin proyecto", form.fields["reason"].help_text)

    def test_empty_submit_returns_spanish_required_errors(self):
        form = MovementForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("Debe seleccionar un producto", form.errors["product"])
        self.assertIn("Debe seleccionar el tipo de movimiento", form.errors["movement_type"])
        self.assertIn("Ingrese la cantidad", form.errors["quantity"])
        self.assertIn("Debe seleccionar un empleado", form.errors["employee"])


class MovementFormQuerySetTest(MovementFormTestBase):
    def test_product_queryset_excludes_inactive(self):
        form = MovementForm()
        pks = set(form.fields["product"].queryset.values_list("pk", flat=True))
        self.assertIn(self.product.pk, pks)
        self.assertNotIn(self.inactive_product.pk, pks)

    def test_employee_queryset_excludes_inactive(self):
        form = MovementForm()
        pks = set(form.fields["employee"].queryset.values_list("pk", flat=True))
        self.assertIn(self.employee.pk, pks)
        self.assertNotIn(self.inactive_employee.pk, pks)

    def test_project_queryset_only_created_and_approved(self):
        form = MovementForm()
        pks = set(form.fields["project"].queryset.values_list("pk", flat=True))
        self.assertIn(self.project_approved.pk, pks)
        self.assertIn(self.project_created.pk, pks)
        self.assertNotIn(self.project_finished.pk, pks)

    def test_optional_selects_have_spanish_empty_labels(self):
        form = MovementForm()
        self.assertEqual(form.fields["product"].empty_label, "Seleccione un producto…")
        self.assertEqual(form.fields["employee"].empty_label, "Seleccione un empleado…")
        self.assertEqual(form.fields["project"].empty_label, "Sin proyecto")

    def test_product_option_label_shows_stock(self):
        form = MovementForm()
        product = form.fields["product"].queryset.get(pk=self.product.pk)
        self.assertIn("stock: 100", form.product_option_label(product))

    def test_selects_render_without_n_plus_one(self):
        form = MovementForm()
        with self.assertNumQueries(3):
            str(form["product"])
            str(form["employee"])
            str(form["project"])


class MovementFormValidationTest(MovementFormTestBase):
    def test_valid_exit_passes(self):
        form = MovementForm(data=self.form_data())
        self.assertTrue(form.is_valid())

    def test_exit_with_reason_instead_of_project_passes(self):
        form = MovementForm(
            data=self.form_data(project="", reason="Uso interno de taller")
        )
        self.assertTrue(form.is_valid())

    def test_exit_requires_project_or_reason(self):
        form = MovementForm(data=self.form_data(project="", reason=""))
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Debe indicar proyecto o motivo de la salida", form.errors["reason"]
        )

    def test_entry_requires_project_or_reason(self):
        form = MovementForm(
            data=self.form_data(
                movement_type=MovementType.ENTRY.value, project="", reason=""
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Debe indicar proyecto o motivo de la entrada", form.errors["reason"]
        )

    def test_exit_rejects_non_approved_project(self):
        form = MovementForm(data=self.form_data(project=self.project_created.pk))
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Solo se puede sacar material para proyectos en curso (Aprobados)",
            form.errors["project"],
        )

    def test_adjustment_requires_type(self):
        form = MovementForm(
            data=self.form_data(
                movement_type=MovementType.ADJUSTMENT.value,
                project="",
                adjustment_type="",
                reason="Corrección de inventario",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Debe seleccionar tipo de ajuste", form.errors["adjustment_type"]
        )

    def test_adjustment_requires_reason(self):
        form = MovementForm(
            data=self.form_data(
                movement_type=MovementType.ADJUSTMENT.value,
                project="",
                adjustment_type=AdjustmentType.IN.value,
                reason="",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Debe ingresar el motivo del ajuste", form.errors["reason"])

    def test_quantity_must_be_positive(self):
        for valor in ("0", "-3"):
            with self.subTest(valor=valor):
                form = MovementForm(data=self.form_data(quantity=valor))
                self.assertFalse(form.is_valid())
                self.assertIn(
                    "La cantidad debe ser mayor a 0", form.errors["quantity"]
                )

    def test_quantity_rejects_non_numeric(self):
        form = MovementForm(data=self.form_data(quantity="abc"))
        self.assertFalse(form.is_valid())
        self.assertIn("Ingrese un número válido", form.errors["quantity"])

    def test_product_invalid_choice(self):
        form = MovementForm(data=self.form_data(product=99999))
        self.assertFalse(form.is_valid())
        self.assertIn(
            "El producto seleccionado no es válido", form.errors["product"]
        )


class MovementCreateViewTest(MovementFormTestBase):
    def setUp(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.client.force_login(self.user)

    def test_get_renders_form(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context["form"], MovementForm)

    def test_prefills_product_from_query_param(self):
        response = self.client.get(self.url(), {"producto": self.product.pk})
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f'<option value="{self.product.pk}" selected',
            response.content.decode(),
        )

    def test_invalid_product_query_param_does_not_break(self):
        response = self.client.get(self.url(), {"producto": "abc"})
        self.assertEqual(response.status_code, 200)

    def test_creates_exit_movement_with_audit_fields(self):
        response = self.client.post(self.url(), self.form_data())
        self.assertRedirects(response, reverse("inventory:historial"))
        movement = Movement.objects.filter(movement_type=MovementType.EXIT).get()
        self.assertEqual(movement.quantity, Decimal("5"))
        self.assertEqual(movement.project, self.project_approved)
        self.assertEqual(movement.warehouse, self.warehouse)
        self.assertEqual(movement.created_by, self.user)
        mensajes = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("Movimiento registrado correctamente", mensajes)

    def test_warehouse_autofilled_from_product(self):
        response = self.client.post(
            self.url(),
            self.form_data(
                movement_type=MovementType.ENTRY.value,
                project="",
                reason="Compra de reposición",
                quantity="20",
            ),
        )
        self.assertRedirects(response, reverse("inventory:historial"))
        movement = Movement.objects.get(reason="Compra de reposición")
        self.assertEqual(movement.warehouse, self.product.warehouse)

    def test_insufficient_stock_shows_form_error(self):
        response = self.client.post(
            self.url(),
            self.form_data(quantity="500"),
            raise_request_exception=False,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stock insuficiente")


class MovementCreateAuthorizationTest(MovementFormTestBase):
    def test_anonymous_get_redirects_to_login(self):
        response = self.client.get(self.url())
        self.assertRedirects(
            response, f"{reverse('login')}?next={self.url()}"
        )

    def test_anonymous_post_redirects_and_creates_nothing(self):
        before = Movement.objects.count()
        response = self.client.post(self.url(), self.form_data())
        self.assertRedirects(
            response, f"{reverse('login')}?next={self.url()}"
        )
        self.assertEqual(Movement.objects.count(), before)

    def test_next_preserves_product_query(self):
        next_url = f"{self.url()}?producto={self.product.pk}"
        response = self.client.get(self.url(), {"producto": self.product.pk})
        self.assertRedirects(response, f"{reverse('login')}?next={next_url}")

        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        login = self.client.post(
            reverse("login"),
            {
                "username": "tester",
                "password": "test1234",
                "next": next_url,
            },
        )
        self.assertRedirects(login, next_url)
        followed = self.client.get(next_url)
        self.assertContains(
            followed, f'<option value="{self.product.pk}" selected'
        )

    def test_staff_creates_movement_with_created_by(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.client.force_login(self.user)
        response = self.client.post(self.url(), self.form_data())
        self.assertRedirects(response, reverse("inventory:historial"))
        movement = Movement.objects.get(movement_type=MovementType.EXIT)
        self.assertEqual(movement.created_by, self.user)

    def test_authenticated_non_staff_is_sent_home_and_creates_nothing(self):
        self.client.force_login(self.user)
        before = Movement.objects.count()
        for method in ("get", "post"):
            with self.subTest(method=method):
                if method == "post":
                    response = self.client.post(
                        self.url(), self.form_data(), follow=True
                    )
                else:
                    response = self.client.get(self.url(), follow=True)
                self.assertRedirects(response, reverse("home"))
                self.assertContains(
                    response,
                    "Tu cuenta no tiene permisos para registrar movimientos.",
                )
                self.assertEqual(Movement.objects.count(), before)

    def test_anonymous_reads_stay_public(self):
        movement = Movement.objects.get(reason="Carga inicial")
        urls = [
            reverse("home"),
            reverse("inventory:historial"),
            reverse("inventory:detalle", args=[movement.pk]),
            reverse("products:products_list"),
            reverse("projects:projects_list"),
            reverse("projects:project_detail", args=[self.project_approved.pk]),
            reverse("employees:employees_list"),
            reverse("employees:employee_detail", args=[self.employee.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)


class MovementModelBaselineTest(MovementFormTestBase):
    """C0 del plan de refactor: congela el comportamiento actual del modelo.

    Estos tests no se modifican durante C1-C3: si el refactor cambia un
    número o un comportamiento, fallan solos.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.product_b = Product.objects.create(
            sku="TST-0100",
            name="Producto baseline B",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
        )
        cls.product_c = Product.objects.create(
            sku="TST-0101",
            name="Producto baseline C",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
        )
        Movement.objects.create(
            product=cls.product_b,
            employee=cls.employee,
            movement_type=MovementType.ENTRY,
            quantity=Decimal("100"),
            reason="Carga inicial",
            created_by=cls.user,
        )
        Movement.objects.create(
            product=cls.product_b,
            employee=cls.employee,
            movement_type=MovementType.EXIT,
            quantity=Decimal("30"),
            project=cls.project_approved,
            reason="Consumo de obra",
            created_by=cls.user,
        )
        Movement.objects.create(
            product=cls.product_b,
            employee=cls.employee,
            movement_type=MovementType.ADJUSTMENT,
            adjustment_type=AdjustmentType.IN,
            quantity=Decimal("10"),
            reason="Sobrante de inventario",
            created_by=cls.user,
        )
        Movement.objects.create(
            product=cls.product_b,
            employee=cls.employee,
            movement_type=MovementType.ADJUSTMENT,
            adjustment_type=AdjustmentType.OUT,
            quantity=Decimal("5"),
            reason="Merma",
            created_by=cls.user,
        )

    def test_manager_exposes_queryset_methods(self):
        self.assertTrue(Movement.objects.for_product(self.product_b).exists())
        self.assertTrue(Movement.objects.entries().exists())
        self.assertTrue(Movement.objects.exits().exists())
        self.assertTrue(Movement.objects.adjustments().exists())
        list(Movement.objects.recent(limit=2))
        list(Movement.objects.for_product(self.product_b).with_signed_quantity())
        self.assertEqual(
            Movement.objects.for_product(self.product_b).stock(), Decimal("75")
        )
        list(Movement.objects.stock_by_product())
        list(Movement.objects.get_products_with_stock())

    def test_get_stock_for_product_exact_number(self):
        self.assertEqual(
            Movement.get_stock_for_product(self.product_b), Decimal("75")
        )
        self.assertEqual(Movement.get_stock_for_product(self.product), Decimal("100"))
        self.assertEqual(Movement.get_stock_for_product(self.product_c), 0)

    def test_get_products_with_stock_rows(self):
        rows = {
            row["product__id"]: row["_stock"]
            for row in Movement.objects.get_products_with_stock()
        }
        self.assertEqual(rows[self.product_b.pk], Decimal("75"))
        self.assertEqual(rows[self.product.pk], Decimal("100"))
        self.assertNotIn(self.product_c.pk, rows)

    def test_signed_quantity_expression_matches_model_property(self):
        movements = Movement.objects.for_product(
            self.product_b
        ).with_signed_quantity()

        for movement in movements:
            with self.subTest(movement=movement.pk):
                self.assertEqual(movement._signed_quantity, movement.signed_quantity)

    def test_stock_by_product_groups_by_product(self):
        rows = {
            row["product"]: row["_stock"]
            for row in Movement.objects.stock_by_product()
        }

        self.assertEqual(rows[self.product_b.pk], Decimal("75"))
        self.assertEqual(rows[self.product.pk], Decimal("100"))
        self.assertNotIn(self.product_c.pk, rows)

    def test_all_stock_entry_points_return_the_same_value(self):
        grouped_stock = next(
            row["_stock"]
            for row in Movement.objects.stock_by_product()
            if row["product"] == self.product_b.pk
        )
        product_stock = Product.objects.with_stock().get(pk=self.product_b.pk).stock

        self.assertEqual(Movement.get_stock_for_product(self.product_b), Decimal("75"))
        self.assertEqual(
            Movement.objects.for_product(self.product_b).stock(), Decimal("75")
        )
        self.assertEqual(grouped_stock, Decimal("75"))
        self.assertEqual(product_stock, Decimal("75"))

    def test_stock_is_zero_without_movements(self):
        self.assertEqual(
            Movement.objects.for_product(self.product_c).stock(), Decimal("0")
        )

    def test_stock_is_independent_of_movement_order(self):
        newest_movement = (
            Movement.objects.for_product(self.product_b)
            .order_by("-created_at")
            .first()
        )

        self.assertEqual(newest_movement.movement_type, MovementType.ADJUSTMENT)
        self.assertEqual(
            Movement.objects.for_product(self.product_b).stock(), Decimal("75")
        )

    def test_signed_quantity_all_types(self):
        movements = {
            (m.movement_type, m.adjustment_type): m.signed_quantity
            for m in Movement.objects.for_product(self.product_b)
        }
        self.assertEqual(movements[(MovementType.ENTRY, None)], Decimal("100"))
        self.assertEqual(movements[(MovementType.EXIT, None)], Decimal("-30"))
        self.assertEqual(movements[(MovementType.ADJUSTMENT, AdjustmentType.IN)], Decimal("10"))
        self.assertEqual(
            movements[(MovementType.ADJUSTMENT, AdjustmentType.OUT)], Decimal("-5")
        )

    def test_recent_activity_structure(self):
        events = recent_activity(limit=10)
        self.assertEqual(len(events), 10)
        for event in events:
            with self.subTest(evento=event["actor"]):
                self.assertEqual(
                    set(event.keys()),
                    {"icon", "fa", "actor", "action", "target", "created_at"},
                )
                self.assertIn(event["icon"], {"danger", "success", "info", "purple"})
        acciones = [event["action"] for event in events]
        self.assertTrue(any("registró" in action for action in acciones))
        self.assertTrue(any("fue creado en el sistema" in action for action in acciones))
        self.assertTrue(any("fue agregado al área de" in action for action in acciones))
        fechas = [event["created_at"] for event in events]
        self.assertEqual(fechas, sorted(fechas, reverse=True))
        self.assertEqual(len(recent_activity(limit=3)), 3)


class RecentActivitySelectorTest(MovementFormTestBase):
    def test_recent_activity_uses_three_queries(self):
        with self.assertNumQueries(3):
            recent_activity(limit=5)

    def test_recent_activity_maps_all_movement_types(self):
        Movement.objects.create(
            product=self.product,
            employee=self.employee,
            movement_type=MovementType.EXIT,
            quantity=Decimal("10"),
            project=self.project_approved,
            reason="Consumo de prueba",
            created_by=self.user,
        )
        Movement.objects.create(
            product=self.product,
            employee=self.employee,
            movement_type=MovementType.ADJUSTMENT,
            adjustment_type=AdjustmentType.IN,
            quantity=Decimal("5"),
            reason="Ajuste de prueba",
            created_by=self.user,
        )
        Movement.objects.create(
            product=self.product,
            employee=self.employee,
            movement_type=MovementType.ADJUSTMENT,
            adjustment_type=AdjustmentType.OUT,
            quantity=Decimal("2"),
            reason="Ajuste de prueba",
            created_by=self.user,
        )

        events = recent_activity(limit=10)
        movement_events = {
            event["action"]: event
            for event in events
            if event["target"] == self.product.name
        }
        expected = {
            "registró una entrada de": ("success", "fa-arrow-down"),
            "registró una salida de": ("danger", "fa-arrow-up"),
            "registró un ajuste de aumento de": ("info", "fa-arrow-up"),
            "registró un ajuste de disminución de": ("info", "fa-arrow-down"),
        }

        for action, (icon, icon_class) in expected.items():
            with self.subTest(action=action):
                self.assertEqual(movement_events[action]["icon"], icon)
                self.assertEqual(movement_events[action]["fa"], icon_class)

    def test_recent_activity_includes_inactive_employees(self):
        actors = {event["actor"] for event in recent_activity(limit=10)}

        self.assertIn("Ana Pérez", actors)
        self.assertIn("Luis López", actors)

    def test_dashboard_renders_recent_activity(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["recent_activity"])
        self.assertContains(response, "Ana Pérez")

    def test_recent_activity_is_not_exposed_by_the_model(self):
        self.assertFalse(hasattr(Movement, "get_recent_activity"))


class DashboardLowStockTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="dashboard-tester", password="test1234"
        )
        cls.warehouse = Warehouse.objects.create(code="DSH-1", name="Almacén dashboard")
        cls.category = Category.objects.create(name="Dashboard low stock")
        cls.unit = Unit.objects.create(name="Cajas", abbreviation="c")
        cls.department = Department.objects.create(name="Dashboard department")
        cls.employee = Employee.objects.create(
            first_name="Dash",
            last_name="Board",
            department=cls.department,
            created_by=cls.user,
        )
        cls.low_products = [
            Product.objects.create(
                sku=f"ALR-{i:04d}",
                name=f"Producto alerta {i:02d}",
                category=cls.category,
                unit=cls.unit,
                warehouse=cls.warehouse,
                minimum_stock=Decimal("10"),
            )
            for i in range(1, 9)
        ]
        cls.healthy = Product.objects.create(
            sku="SAN-0001",
            name="Producto con stock sano",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
            minimum_stock=Decimal("10"),
        )
        Movement.objects.create(
            product=cls.healthy,
            employee=cls.employee,
            movement_type=MovementType.ENTRY,
            quantity=Decimal("50"),
            reason="Carga inicial",
            created_by=cls.user,
        )

    def test_dashboard_reports_the_total_low_stock_count(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["low_stock_count"], 8)

    def test_dashboard_limits_the_displayed_low_stock_products(self):
        response = self.client.get(reverse("home"))

        products = response.context["low_stock_products"]
        self.assertEqual(len(products), LOW_STOCK_DISPLAY_LIMIT)
        self.assertEqual(
            [product.sku for product in products],
            [f"ALR-{i:04d}" for i in range(1, 7)],
        )

    def test_low_stock_count_and_slice_use_two_queries(self):
        qs = Product.objects.low_stock()

        with self.assertNumQueries(2):
            total = qs.count()
            products = list(qs[:LOW_STOCK_DISPLAY_LIMIT])

        self.assertEqual(total, 8)
        self.assertEqual(len(products), LOW_STOCK_DISPLAY_LIMIT)

    def test_dashboard_uses_seven_queries(self):
        # 2 del bloque de stock bajo (COUNT + LIMIT 6) + 1 movimientos
        # + 1 proyectos + 3 del feed de actividad = 7. Cliente anónimo
        # para que session/auth no añadan consultas de middleware.
        with self.assertNumQueries(7):
            self.client.get(reverse("home"))

    def test_dashboard_renders_the_total_in_the_badge(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "8 productos")

    def test_dashboard_renders_only_six_alerts(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "Producto alerta 01")
        self.assertContains(response, "Producto alerta 06")
        self.assertNotContains(response, "Producto alerta 07")


class RegisterMovementServiceTest(MovementFormTestBase):
    def test_creates_movement_and_returns_the_instance(self):
        movement = register_movement(
            product=self.product,
            employee=self.employee,
            movement_type=MovementType.ENTRY,
            quantity=Decimal("10"),
            reason="Compra de reposición",
            created_by=self.user,
        )

        self.assertIsInstance(movement, Movement)
        self.assertTrue(Movement.objects.filter(pk=movement.pk).exists())
        self.assertEqual(movement.created_by, self.user)
        self.assertEqual(movement.warehouse, self.product.warehouse)

    def test_movement_changes_stock_through_the_same_rule(self):
        register_movement(
            product=self.product,
            employee=self.employee,
            movement_type=MovementType.EXIT,
            quantity=Decimal("5"),
            project=self.project_approved,
            created_by=self.user,
        )

        self.assertEqual(Movement.get_stock_for_product(self.product), Decimal("95"))

    def test_insufficient_stock_raises_and_persists_nothing(self):
        movements_before = Movement.objects.count()

        with self.assertRaises(ValidationError) as ctx:
            register_movement(
                product=self.product,
                employee=self.employee,
                movement_type=MovementType.EXIT,
                quantity=Decimal("500"),
                project=self.project_approved,
                created_by=self.user,
            )

        self.assertIn("Stock insuficiente", ctx.exception.messages[0])
        self.assertEqual(Movement.objects.count(), movements_before)

    def test_exit_without_project_or_reason_raises_and_persists_nothing(self):
        movements_before = Movement.objects.count()

        with self.assertRaises(ValidationError):
            register_movement(
                product=self.product,
                employee=self.employee,
                movement_type=MovementType.EXIT,
                quantity=Decimal("5"),
                created_by=self.user,
            )

        self.assertEqual(Movement.objects.count(), movements_before)

    def test_adjustment_requires_type_and_reason(self):
        movements_before = Movement.objects.count()

        with self.assertRaises(ValidationError):
            register_movement(
                product=self.product,
                employee=self.employee,
                movement_type=MovementType.ADJUSTMENT,
                quantity=Decimal("5"),
                created_by=self.user,
            )

        self.assertEqual(Movement.objects.count(), movements_before)


class MovementConstraintsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="constraint-tester", password="test1234"
        )
        cls.warehouse = Warehouse.objects.create(code="CON-1", name="Almacén constraints")
        cls.category = Category.objects.create(name="Constraints")
        cls.unit = Unit.objects.create(name="Unidades C", abbreviation="uc")
        cls.department = Department.objects.create(name="Constraints department")
        cls.employee = Employee.objects.create(
            first_name="Con",
            last_name="Straint",
            department=cls.department,
            created_by=cls.user,
        )
        cls.product = Product.objects.create(
            sku="CON-0001",
            name="Producto constraints",
            category=cls.category,
            unit=cls.unit,
            warehouse=cls.warehouse,
        )

    def movement(self, **overrides):
        data = {
            "product": self.product,
            "employee": self.employee,
            "movement_type": MovementType.ENTRY,
            "quantity": Decimal("10"),
            "reason": "Prueba de constraints",
            "created_by": self.user,
        }
        data.update(overrides)
        return Movement(**data)

    def test_bulk_create_rejects_zero_and_negative_quantity(self):
        for quantity in (Decimal("0"), Decimal("-5")):
            with self.subTest(quantity=quantity):
                with self.assertRaises(IntegrityError):
                    # bulk_create envuelve su INSERT en atomic(savepoint=False):
                    # al fallar deja la transacción rota; este savepoint
                    # externo la restaura para el siguiente subTest.
                    with transaction.atomic():
                        Movement.objects.bulk_create(
                            [self.movement(quantity=quantity)]
                        )

    def test_bulk_create_accepts_valid_rows(self):
        Movement.objects.bulk_create([self.movement()])

        self.assertEqual(Movement.objects.count(), 1)

    def test_full_clean_reports_quantity_violation(self):
        with self.assertRaises(ValidationError):
            self.movement(quantity=Decimal("0")).full_clean()

    def test_bulk_create_rejects_adjustment_without_type(self):
        movement = self.movement(
            movement_type=MovementType.ADJUSTMENT,
            reason="Ajuste de prueba",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Movement.objects.bulk_create([movement])

    def test_bulk_create_rejects_non_adjustment_with_type(self):
        for adjustment_type in (AdjustmentType.IN, "XX"):
            with self.subTest(adjustment_type=adjustment_type):
                movement = self.movement(adjustment_type=adjustment_type)
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        Movement.objects.bulk_create([movement])

    def test_validate_constraints_reports_adjustment_incoherence(self):
        movement = self.movement(
            movement_type=MovementType.ADJUSTMENT,
            reason="Ajuste de prueba",
        )
        with self.assertRaises(ValidationError):
            movement.validate_constraints()


class MovementIndexesTest(TestCase):
    def test_movement_meta_indexes_match_the_measured_set(self):
        names = {index.name for index in Movement._meta.indexes}

        self.assertEqual(
            names,
            {
                "inventory_m_movemen_6d66c7_idx",
                "inventory_m_created_b65c6f_idx",
            },
        )


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentRegisterMovementTest(TransactionTestCase):
    """Dos salidas simultáneas no pueden dejar el stock en negativo.

    TransactionTestCase (commits reales) porque TestCase envuelve todo
    en transacciones: cada hilo abriría su propia conexión y no vería
    los datos no confirmados del otro, ocultando la carrera.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="concurrent-tester", password="test1234"
        )
        self.warehouse = Warehouse.objects.create(code="CONC-1", name="Almacén concurrencia")
        self.category = Category.objects.create(name="Concurrencia")
        self.unit = Unit.objects.create(name="Piezas C", abbreviation="pc")
        self.department = Department.objects.create(name="Departamento concurrencia")
        self.employee = Employee.objects.create(
            first_name="Con",
            last_name="Current",
            department=self.department,
            created_by=self.user,
        )
        self.product = Product.objects.create(
            sku="CONC-0001",
            name="Producto concurrencia",
            category=self.category,
            unit=self.unit,
            warehouse=self.warehouse,
        )
        Movement.objects.create(
            product=self.product,
            employee=self.employee,
            movement_type=MovementType.ENTRY,
            quantity=Decimal("100"),
            reason="Carga inicial",
            created_by=self.user,
        )

    def test_two_concurrent_exits_serialize_on_the_product(self):
        barrier = threading.Barrier(2)
        results = []

        def worker():
            from django.db import connection

            try:
                barrier.wait(timeout=10)
                register_movement(
                    product=self.product,
                    employee=self.employee,
                    movement_type=MovementType.EXIT,
                    quantity=Decimal("80"),
                    reason="Salida concurrente",
                    created_by=self.user,
                )
                results.append("ok")
            except ValidationError:
                results.append("stock-insuficiente")
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(sorted(results), ["ok", "stock-insuficiente"])
        self.assertEqual(Movement.get_stock_for_product(self.product), Decimal("20"))
        self.assertEqual(
            Movement.objects.filter(movement_type=MovementType.EXIT).count(), 1
        )


class MovementHistoryTest(MovementFormTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for i in range(25):
            Movement.objects.create(
                product=cls.product,
                employee=cls.employee,
                movement_type=MovementType.ENTRY,
                quantity=Decimal("10"),
                reason=f"Carga histórica {i}",
                created_by=cls.user,
            )
        for i in range(3):
            Movement.objects.create(
                product=cls.product,
                employee=cls.employee,
                movement_type=MovementType.EXIT,
                quantity=Decimal("2"),
                project=cls.project_approved,
                created_by=cls.user,
            )

    def test_history_renders_and_paginates(self):
        response = self.client.get(reverse("inventory:historial"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["movements"]), 20)
        self.assertEqual(response.context["paginator"].count, 29)
        self.assertEqual(response.context["paginator"].num_pages, 2)

    def test_history_orders_newest_first(self):
        response = self.client.get(reverse("inventory:historial"))

        newest = Movement.objects.order_by("-created_at").first()
        self.assertEqual(response.context["movements"][0].pk, newest.pk)

    def test_history_filters_by_type(self):
        response = self.client.get(
            reverse("inventory:historial"), {"movement_type": MovementType.EXIT}
        )

        movements = response.context["movements"]
        self.assertEqual(response.context["paginator"].count, 3)
        self.assertTrue(
            all(m.movement_type == MovementType.EXIT for m in movements)
        )

    def test_history_search_matches_sku_and_name(self):
        response = self.client.get(
            reverse("inventory:historial"), {"q": self.product.sku}
        )

        self.assertEqual(response.context["paginator"].count, 29)
        self.assertTrue(
            all(m.product == self.product for m in response.context["movements"])
        )

    def test_history_filters_by_date_range(self):
        Movement.objects.filter(reason="Carga histórica 0").update(
            created_at=timezone.now() - timedelta(days=30)
        )
        today = timezone.localdate()

        response = self.client.get(
            reverse("inventory:historial"), {"desde": today.isoformat()}
        )
        self.assertEqual(response.context["paginator"].count, 28)

        response = self.client.get(
            reverse("inventory:historial"),
            {"hasta": (today - timedelta(days=1)).isoformat()},
        )
        self.assertEqual(response.context["paginator"].count, 1)

    def test_history_uses_select_related(self):
        with self.assertNumQueries(2):
            self.client.get(reverse("inventory:historial"))

    def test_history_renders_empty_state(self):
        response = self.client.get(
            reverse("inventory:historial"), {"q": "no-existe-zzz"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sin resultados")

    def test_detail_renders_all_fields(self):
        movement = Movement.objects.filter(
            movement_type=MovementType.EXIT
        ).first()

        response = self.client.get(reverse("inventory:detalle", args=[movement.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, movement.product.name)
        self.assertContains(response, movement.product.sku)
        self.assertContains(response, "Salida")
        self.assertContains(response, movement.employee.full_name)

    def test_detail_404_for_unknown_pk(self):
        response = self.client.get(reverse("inventory:detalle", args=[99999]))

        self.assertEqual(response.status_code, 404)
