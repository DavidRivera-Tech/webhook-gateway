"""
Load test for the Webhook Delivery Gateway.

Simulates many concurrent clients sending webhook events to the API, to verify
that the API stays responsive under burst traffic. Because the API offloads
delivery to a background worker (returning 202 immediately), it should handle
high concurrency without blocking — this test demonstrates that.

Run:
    locust -f loadtest/locustfile.py --host http://localhost:8000

Then open http://localhost:8089, set the number of users (e.g. 1000) and spawn
rate, and start. Watch requests/sec and response times in the dashboard.
"""

from locust import HttpUser, task, between


class WebhookSender(HttpUser):
    # Each simulated user waits 0.1–0.5s between requests (realistic pacing).
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Runs once when a simulated user starts: register an endpoint to
        send events to, and remember its id for the load test."""
        response = self.client.post(
            "/endpoints",
            json={"url": "https://httpbin.org/post", "name": "loadtest-target"},
        )
        if response.status_code == 201:
            self.endpoint_id = response.json()["id"]
        else:
            self.endpoint_id = 1  # fallback

    @task
    def send_webhook(self):
        """The main load: fire a webhook event at the API and expect a fast 202."""
        self.client.post(
            "/webhooks",
            json={"endpoint_id": self.endpoint_id, "payload": '{"load":"test"}'},
            name="/webhooks",  # groups all these in the stats
        )
