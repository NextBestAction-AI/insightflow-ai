import unittest

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class FrontendRoutesTestCase(unittest.TestCase):
    def test_root_endpoint(self):
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Online")

    def test_health_endpoint(self):
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)

    def test_frontend_endpoints_return_fallback_payloads(self):
        analyze_response = client.post("/api/analyze", json={"interaction_id": 1})
        self.assertEqual(analyze_response.status_code, 201)
        self.assertIsInstance(analyze_response.json(), list)

        upload_response = client.post(
            "/api/upload",
            json={"customer_id": 1, "content": "hello world"},
        )
        self.assertEqual(upload_response.status_code, 201)
        self.assertEqual(upload_response.json()["message"], "uploaded")

        workflow_response = client.get("/api/workflow-status")
        self.assertEqual(workflow_response.status_code, 200)

        recommendation_response = client.get("/api/recommendation")
        self.assertEqual(recommendation_response.status_code, 200)

        customer_health_response = client.get("/api/customer-health")
        self.assertEqual(customer_health_response.status_code, 200)

        approve_response = client.post("/api/approve", json={"recommendation_id": 1})
        self.assertEqual(approve_response.status_code, 201)

        reject_response = client.post("/api/reject", json={"recommendation_id": 1})
        self.assertEqual(reject_response.status_code, 201)


if __name__ == "__main__":
    unittest.main()
