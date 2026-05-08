from app.seed.seed_model_metadata import MODEL_INPUT_SCHEMA, MODEL_METADATA
from app.seed.seed_promocodes import (
    POINCARE_CHALLENGE_WORDING_EN,
    POINCARE_CHALLENGE_WORDING_RU,
    PROMOCODE_DEFINITIONS,
)


EXPECTED_FEATURES = [
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
]


def get_promocode_definition(code: str) -> dict:
    return next(item for item in PROMOCODE_DEFINITIONS if item["code"] == code)


def test_model_input_schema_contains_expected_features() -> None:
    assert MODEL_METADATA["name"] == "hotel_cancellation_model"
    assert MODEL_INPUT_SCHEMA["features"] == EXPECTED_FEATURES
    assert MODEL_INPUT_SCHEMA["target"] == "is_canceled"


def test_model_input_schema_excludes_leakage_columns() -> None:
    assert MODEL_INPUT_SCHEMA["leakage_excluded"] == [
        "reservation_status",
        "reservation_status_date",
    ]


def test_seed_promocodes_definitions_include_welcome100() -> None:
    promocode = get_promocode_definition("WELCOME100")

    assert promocode["credits_amount"] == 100
    assert promocode["max_activations"] == 100000
    assert promocode["is_active"] is True


def test_seed_promocodes_definitions_include_anisimov100() -> None:
    promocode = get_promocode_definition("ANISIMOV100")

    assert promocode["credits_amount"] == 100
    assert "Анисимов Ян Олегович" in promocode["description"]


def test_seed_promocodes_definitions_include_springfield100() -> None:
    promocode = get_promocode_definition("SPRINGFIELD100")

    assert promocode["credits_amount"] == 100
    assert "cartoon-style" in promocode["description"]


def test_seed_promocodes_definitions_include_poincare_challenge() -> None:
    promocode = get_promocode_definition("POINCARE_CHALLENGE")

    assert promocode["credits_amount"] == 1000
    assert "Poincaré conjecture proof" in promocode["description"]


def test_poincare_challenge_wording_is_present() -> None:
    assert (
        "Всякое замкнутое односвязное трёхмерное многообразие"
        in POINCARE_CHALLENGE_WORDING_RU
    )
    assert (
        POINCARE_CHALLENGE_WORDING_EN
        == "Every simply connected, closed 3-manifold is homeomorphic to the 3-sphere."
    )


def test_seed_definitions_do_not_reset_current_activations_field() -> None:
    assert all(
        "current_activations" not in definition
        for definition in PROMOCODE_DEFINITIONS
    )
