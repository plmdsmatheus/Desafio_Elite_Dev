import pytest

from apps.accounts.models import User


@pytest.mark.django_db
class TestRegister:
    def test_register_always_creates_customer_role(self, api_client):
        response = api_client.post(
            "/api/auth/register",
            {"email": "new@test.com", "password": "senha12345"},
            format="json",
        )
        assert response.status_code == 201
        user = User.objects.get(email="new@test.com")
        assert user.role == User.Role.CUSTOMER
        assert user.check_password("senha12345")

    def test_register_ignores_role_in_payload(self, api_client):
        """Ninguém vira organizador/portaria só mandando "role" no corpo do cadastro público."""
        response = api_client.post(
            "/api/auth/register",
            {"email": "sneaky@test.com", "password": "senha12345", "role": "organizer"},
            format="json",
        )
        assert response.status_code == 201
        assert User.objects.get(email="sneaky@test.com").role == User.Role.CUSTOMER


@pytest.mark.django_db
class TestLoginAndMe:
    def test_login_returns_tokens_and_user_payload(self, api_client, customer):
        response = api_client.post(
            "/api/auth/login", {"email": customer.email, "password": "x"}, format="json"
        )
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["email"] == customer.email
        assert response.data["user"]["role"] == "customer"

    def test_login_with_wrong_password_fails(self, api_client, customer):
        response = api_client.post(
            "/api/auth/login", {"email": customer.email, "password": "wrong"}, format="json"
        )
        assert response.status_code == 401

    def test_me_with_real_bearer_token_from_login(self, api_client, customer):
        """Fim a fim de verdade via header Authorization, sem force_authenticate — o
        mesmo caminho que o Swagger UI percorre ao clicar em "Authorize"."""
        login = api_client.post(
            "/api/auth/login", {"email": customer.email, "password": "x"}, format="json"
        )
        access = login.data["access"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = api_client.get("/api/auth/me")

        assert response.status_code == 200
        assert response.data["email"] == customer.email

    def test_me_requires_authentication(self, api_client):
        response = api_client.get("/api/auth/me")
        assert response.status_code == 401
