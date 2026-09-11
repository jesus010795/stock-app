from django import forms

from .models import Movement


class MovementForm(forms.ModelForm):
    class Meta:
        model = Movement
        fields = [
            "product",
            "movement_type",
            "adjustment_type",
            "quantity",
            "warehouse",
            "employee",
            "project",
            "reason",
        ]
        labels = {
            "product": "Producto",
            "movement_type": "Tipo de movimiento",
            "adjustment_type": "Tipo de ajuste",
            "warehouse": "Almacén",
            "project": "Proyecto",
            "reason": "Motivo",
        }
        widgets = {
            "product": forms.Select(attrs={"class": "select"}),
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
            "warehouse": forms.Select(attrs={"class": "select"}),
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
            "warehouse": {"invalid_choice": "El almacén seleccionado no es válido"},
            "project": {"invalid_choice": "El proyecto seleccionado no es válido"},
        }
