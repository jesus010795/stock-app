from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class StaffLoginTests(TestCase):
    def setUp(self):
        self.login_url = reverse("login")
        self.home_url = reverse("home")
        self.staff = User.objects.create_user(
            username="staff",
            password="secret123",
            is_staff=True,
        )

    def test_get_login_returns_200(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)

    def test_login_texts_in_spanish(self):
        response = self.client.get(self.login_url)
        self.assertContains(response, "Iniciar sesión")
        self.assertContains(response, "Usuario")
        self.assertContains(response, "Contraseña")

    def test_staff_login_creates_session(self):
        response = self.client.post(
            self.login_url,
            {"username": "staff", "password": "secret123"},
        )
        self.assertRedirects(response, self.home_url)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_without_next_redirects_home(self):
        response = self.client.post(
            self.login_url,
            {"username": "staff", "password": "secret123", "next": ""},
        )
        self.assertRedirects(response, self.home_url)

    def test_login_honors_internal_next(self):
        next_url = reverse("inventory:nuevo")
        form_page = self.client.get(self.login_url, {"next": next_url})
        self.assertContains(form_page, f'name="next" value="{next_url}"')

        response = self.client.post(
            self.login_url,
            {
                "username": "staff",
                "password": "secret123",
                "next": next_url,
            },
        )
        self.assertRedirects(response, next_url)

    def test_external_next_is_ignored(self):
        response = self.client.post(
            self.login_url,
            {
                "username": "staff",
                "password": "secret123",
                "next": "https://evil.example/phish",
            },
        )
        self.assertRedirects(response, self.home_url)

    def test_bad_credentials_show_generic_error_and_no_session(self):
        response = self.client.post(
            self.login_url,
            {"username": "staff", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "El usuario o la contraseña son incorrectos."
        )
        self.assertNotContains(response, "no tiene permisos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_gets_the_same_generic_error(self):
        User.objects.create_user(
            username="inactive",
            password="secret123",
            is_staff=True,
            is_active=False,
        )
        response = self.client.post(
            self.login_url,
            {"username": "inactive", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "El usuario o la contraseña son incorrectos."
        )
        self.assertNotContains(response, "inactiva")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_active_non_staff_is_rejected(self):
        User.objects.create_user(username="nostaff", password="secret123")
        response = self.client.post(
            self.login_url,
            {"username": "nostaff", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Tu cuenta no tiene permisos para acceder a esta aplicación.",
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_user_opening_login_redirects_home(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.login_url)
        self.assertRedirects(response, self.home_url)

    def test_get_logout_returns_405(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)

    def test_post_logout_destroys_session_and_redirects_home(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, self.home_url)
        self.assertNotIn("_auth_user_id", self.client.session)
