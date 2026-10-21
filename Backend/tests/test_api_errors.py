import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from app.core import config
from app.core.errors import install_error_handlers
from app.migrations.runner import migrate_database
from app.schemas.auth import RegisterRequest


class RequestValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir_patch = patch.object(config, "BASE_DIR", self.temp_dir.name)
        self.base_dir_patch.start()
        migrate_database(Path(self.temp_dir.name) / "complaints.db")

    def tearDown(self):
        self.base_dir_patch.stop()
        self.temp_dir.cleanup()

    def test_valid_auth_request_model_is_accepted(self):
        request = RegisterRequest(
            name="Test Citizen",
            email="citizen@example.com",
            password="valid-password",
        )
        self.assertEqual(request.email, "citizen@example.com")

    def test_invalid_body_is_422_and_does_not_echo_password(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/register",
                json={
                    "name": "A",
                    "email": "not-an-email",
                    "password": "secret-password",
                },
            )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["code"], "validation_error")
        self.assertEqual(body["detail"], "Request validation failed")
        self.assertNotIn("input", str(body).lower())
        self.assertNotIn("secret-password", str(body))

    def test_invalid_query_and_path_values_are_rejected(self):
        main.app.dependency_overrides[main.get_current_user] = lambda: {
            "id": 1,
            "name": "Test Citizen",
            "email": "citizen@example.com",
            "role": "citizen",
        }
        with TestClient(main.app) as client:
            status_response = client.get("/my-complaints?status=Unknown")
            id_response = client.get("/my-complaints/0")
        main.app.dependency_overrides.clear()
        self.assertEqual(status_response.status_code, 422)
        self.assertEqual(id_response.status_code, 422)
        self.assertEqual(status_response.json()["code"], "validation_error")
        self.assertEqual(id_response.json()["code"], "validation_error")
        client.close()

    def test_authentication_errors_have_consistent_codes(self):
        with TestClient(main.app) as client:
            response = client.get("/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "authentication_required")

    def test_permission_errors_have_consistent_codes(self):
        main.app.dependency_overrides[main.get_current_user] = lambda: {
            "id": 1,
            "name": "Test Citizen",
            "email": "citizen@example.com",
            "role": "citizen",
        }
        try:
            with TestClient(main.app) as client:
                response = client.get("/admin/officers")
        finally:
            main.app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "permission_denied")

    def test_unexpected_error_is_logged_and_sanitized(self):
        app = FastAPI()
        install_error_handlers(app)

        @app.get("/failure")
        def failure():
            raise RuntimeError("secret internal detail")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/failure")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["code"], "internal_server_error")
        self.assertNotIn("secret internal detail", response.text)
        client.close()

    def test_database_error_is_sanitized(self):
        app = FastAPI()
        install_error_handlers(app)

        @app.get("/database-failure")
        def database_failure():
            raise sqlite3.OperationalError("sensitive database detail")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/database-failure")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["code"], "internal_server_error")
        self.assertNotIn("sensitive database detail", response.text)
        client.close()


if __name__ == "__main__":
    unittest.main()
