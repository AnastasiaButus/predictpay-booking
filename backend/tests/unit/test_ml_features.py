from app.ml.features import (
    CATEGORICAL_FEATURES,
    DEFAULT_MODEL_PATH,
    FEATURE_COLUMNS,
    LEAKAGE_COLUMNS,
    NUMERIC_FEATURES,
)


EXPECTED_FEATURE_COLUMNS = [
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


def test_feature_columns_match_expected_contract() -> None:
    assert FEATURE_COLUMNS == EXPECTED_FEATURE_COLUMNS


def test_categorical_and_numeric_features_partition_feature_columns() -> None:
    combined = set(CATEGORICAL_FEATURES) | set(NUMERIC_FEATURES)

    assert combined == set(FEATURE_COLUMNS)
    assert set(CATEGORICAL_FEATURES).isdisjoint(NUMERIC_FEATURES)


def test_leakage_columns_not_in_feature_columns() -> None:
    assert set(LEAKAGE_COLUMNS).isdisjoint(FEATURE_COLUMNS)


def test_expected_model_path_matches_seed_metadata_path() -> None:
    assert DEFAULT_MODEL_PATH == "storage/models/hotel_cancellation_model.joblib"
