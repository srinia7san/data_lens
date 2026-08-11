import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from routes.api import session_store
from routes.server import app


class ApiSmokeTests(unittest.TestCase):
    def setUp(self):
        session_store.clear()
        self.client = TestClient(app)

    def _auth_headers(self):
        email = f"smoke-{uuid.uuid4().hex}@example.com"
        response = self.client.post(
            "/api/v1/auth/signup",
            json={
                "name": "Smoke User",
                "email": email,
                "password": "password123",
            },
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def test_health_endpoints(self):
        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.json()["status"], "healthy")

        api_health = self.client.get("/api/v1/health")
        self.assertEqual(api_health.status_code, 200)
        self.assertEqual(api_health.json(), {"status": "healthy", "sessions": 0})

    def test_connection_lifecycle(self):
        headers = self._auth_headers()
        created = self.client.post(
            "/api/v1/connections",
            headers=headers,
            json={
                "name": "local",
                "connection_string": "sqlite:///example.db",
                "db_dialect": "SQLite",
            },
        )
        self.assertEqual(created.status_code, 200)
        body = created.json()
        self.assertEqual(body["active_connection"], "local")

        listed = self.client.get(
            "/api/v1/connections",
            headers=headers,
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["connections"]), 1)

        removed = self.client.request(
            "DELETE",
            "/api/v1/connections",
            headers=headers,
            json={"name": "local", "session_id": "authenticated"},
        )
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(removed.json()["active_connection"])

    def test_auth_login_and_me(self):
        email = f"auth-{uuid.uuid4().hex}@example.com"
        password = "password123"
        created = self.client.post(
            "/api/v1/auth/signup",
            json={"name": "Auth User", "email": email, "password": password},
        )
        self.assertEqual(created.status_code, 200)

        logged_in = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(logged_in.status_code, 200)
        token = logged_in.json()["token"]

        me = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["email"], email)

    def test_chat_without_connection_does_not_import_pipeline(self):
        headers = self._auth_headers()
        response = self.client.post(
            "/api/v1/chat",
            headers=headers,
            json={"user_message": "show total sales", "response_mode": "both"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "error")
        self.assertIn("No database connection", response.json()["reply"])

    def test_report_endpoint_rejects_arbitrary_paths(self):
        response = self.client.get("/api/v1/report", params={"path": __file__})
        self.assertEqual(response.status_code, 400)

    def test_report_endpoint_serves_generated_report_files(self):
        report_path = Path(tempfile.gettempdir()) / "da_report_smoke.html"
        report_path.write_text("<html><body>ok</body></html>", encoding="utf-8")
        try:
            response = self.client.get(
                "/api/v1/report",
                params={"path": str(report_path)},
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("ok", response.text)
        finally:
            report_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
