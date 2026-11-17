from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class StaffLoginForm(AuthenticationForm):
    """Login del frontend: solo usuarios activos con is_staff=True.

    El backend por defecto no entrega usuarios inactivos a
    confirm_login_allowed(); esos casos caen en invalid_login, el mismo
    mensaje genérico que una contraseña incorrecta.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "El usuario o la contraseña son incorrectos.",
        "not_staff": (
            "Tu cuenta no tiene permisos para acceder a esta aplicación."
        ),
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Usuario"
        self.fields["username"].widget.attrs.update(
            {
                "class": "input",
                "autofocus": True,
                "autocomplete": "username",
            }
        )
        self.fields["password"].label = "Contraseña"
        self.fields["password"].widget.attrs.update(
            {
                "class": "input",
                "autocomplete": "current-password",
            }
        )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError(
                self.error_messages["not_staff"],
                code="not_staff",
            )
