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