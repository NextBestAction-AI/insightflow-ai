import unittest
from fastapi.testclient import TestClient

from app.main import app


class AppStartupTestCase(unittest.TestCase):
    def test_root_endpoint(self):
        client = TestClient(app)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Online")


if __name__ == "__main__":
    unittest.main()
