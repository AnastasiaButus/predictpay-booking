EXPECTED_BOOKING_FEATURES = {
    "hotel",
    "lead_time",
    "adults",
    "children",
    "previous_cancellations",
    "booking_changes",
    "deposit_type",
    "customer_type",
    "market_segment",
    "required_car_parking_spaces",
    "total_of_special_requests",
    "adr",
}


def test_user_payloads(valid_user_payload: dict, admin_user_payload: dict) -> None:
    assert valid_user_payload["email"] == "demo@example.com"
    assert valid_user_payload["password"]
    assert admin_user_payload["email"] == "admin@example.com"
    assert admin_user_payload["password"]


def test_booking_payloads(
    valid_booking_payload: dict, invalid_booking_payload: dict
) -> None:
    assert "model_id" in valid_booking_payload
    assert "features" in valid_booking_payload
    assert set(valid_booking_payload["features"]) == EXPECTED_BOOKING_FEATURES

    assert invalid_booking_payload != valid_booking_payload
    assert invalid_booking_payload["features"]["adr"] == -1


def test_promocode_payloads(
    welcome_promocode_payload: dict, poincare_challenge_payload: dict
) -> None:
    assert welcome_promocode_payload["code"] == "WELCOME100"
    assert "proof_url" in poincare_challenge_payload
