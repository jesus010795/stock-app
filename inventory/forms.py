from django import forms

from employees.models import Employee
from products.models import Product
from projects.models import Project

from .models import Movement, MovementType


class MovementForm(forms.ModelForm):
    class Meta:
        model = Movement
        fields = [
            "product",
            "movement_type",
            "adjustment_type",
            "quantity",
            "employee",
            "project",
            "reason",
        ]
        labels = {
            "product": "Producto",
            "movement_type": "Tipo de movimiento",
            "adjustment_type": "Tipo de ajuste",
            "project": "Proyecto",
            "reason": "Motivo",
        }
        widgets = {
            # El producto no se elige de un desplegable: el campo queda
            # oculto y la plantilla monta un buscador con autocompletado
            # (templates/inventory/movimiento_form.html + static/js/
            # product-autocomplete.js) contra el endpoint JSON
            # inventory:buscar-productos. La validación del pk no cambia:
            # ModelChoiceField sigue rechazando valores fuera del queryset.
            "product": forms.HiddenInput(),
            "movement_type": forms.Select(attrs={"class": "select"}),
            "adjustment_type": forms.Select(attrs={"class": "select"}),
            "quantity": forms.NumberInput(
                attrs={
                    "class": "input",
                    "step": "0.01",
                    "min": "0.01",
                    "inputmode": "decimal",
                }
            ),
            "employee": forms.Select(attrs={"class": "select"}),
            "project": forms.Select(attrs={"class": "select"}),
            "reason": forms.Textarea(
                attrs={
                    "class": "textarea",
                    "rows": 3,
                    "placeholder": "Ej. reposición de material, consumo para obra, corrección de inventario",
                }
            ),
        }
        help_texts = {
            "product": "Escriba al menos 2 caracteres y seleccione una opción de la lista",
            "movement_type": "Entrada, salida o ajuste de inventario",
            "adjustment_type": "Solo aplica para ajustes",
            "employee": "Quién solicita o registra el movimiento",
            "project": "Para salidas solo se permiten proyectos en curso (aprobados)",
            "reason": "Obligatorio en salidas sin proyecto y en todo ajuste",
        }
        error_messages = {
            "product": {
                "required": "Debe seleccionar un producto",
                "invalid_choice": "El producto seleccionado no es válido",
            },
            "movement_type": {"required": "Debe seleccionar el tipo de movimiento"},
            "quantity": {
                "required": "Ingrese la cantidad",
                "invalid": "Ingrese un número válido",
            },
            "employee": {
                "required": "Debe seleccionar un empleado",
                "invalid_choice": "El empleado seleccionado no es válido",
            },
            "project": {"invalid_choice": "El proyecto seleccionado no es válido"},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Queryset de validación: solo productos activos. El desplegable
        # con las opciones ya no existe (ver widgets["product"]); la
        # etiqueta de cada opción la arma selectors.product_label y la
        # consume el endpoint de autocompletado. Sin with_stock(): el
        # ModelChoiceField con HiddenInput solo necesita validar el pk.
        self.fields["product"].queryset = Product.objects.active()
        self.fields["employee"].queryset = Employee.objects.filter(
            is_active=True
        ).select_related("department")
        self.fields["employee"].empty_label = "Seleccione un empleado…"
        self.fields["project"].queryset = Project.objects.active()
        self.fields["project"].empty_label = "Sin proyecto"


class MovementFilterForm(forms.Form):
    """Filtros del historial de movimientos (GET, sin persistencia)."""

    movement_type = forms.ChoiceField(
        choices=[("", "Todos los tipos")] + MovementType.choices,
        required=False,
        label="Tipo de movimiento",
        widget=forms.Select(attrs={"class": "select"}),
    )
    q = forms.CharField(
        required=False,
        label="Búsqueda",
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "Buscar por producto o SKU…",
            }
        ),
    )
    desde = forms.DateField(
        required=False,
        label="Desde",
        widget=forms.DateInput(attrs={"class": "input", "type": "date"}),
    )
    hasta = forms.DateField(
        required=False,
        label="Hasta",
        widget=forms.DateInput(attrs={"class": "input", "type": "date"}),
    )
