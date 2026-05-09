from fastapi.testclient import TestClient


def test_metrics_endpoint_returns_prometheus_text(client: TestClient) -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "predictpay_http_requests_total" in response.text
    assert "predictpay_app_info" in response.text


def test_metrics_endpoint_contains_expected_metric_names(client: TestClient) -> None:
    response = client.get("/metrics")

    assert "predictpay_http_request_duration_seconds" in response.text
    assert "predictpay_predictions_submitted_total" in response.text


def test_request_id_generated_or_preserved(client: TestClient) -> None:
    generated_response = client.get("/api/v1/users/me")
    preserved_response = client.get(
        "/api/v1/users/me",
        headers={"X-Request-ID": "test-request-id"},
    )

    assert generated_response.headers["X-Request-ID"]
    assert preserved_response.headers["X-Request-ID"] == "test-request-id"


def test_health_still_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
