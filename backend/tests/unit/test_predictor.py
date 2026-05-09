from pathlib import Path
from typing import Any

import joblib
import pytest

from app.core.exceptions import InvalidFeaturePayloadError, ModelNotFoundError
from app.ml.features import FEATURE_COLUMNS
from app.ml.predictor import HotelCancellationPredictor
from app.ml.train_model import build_pipeline, create_synthetic_dataset, prepare_training_data


VALID_FEATURES = {
    "hotel": "City Hotel",
    "lead_time": 120,
    "adults": 2,
    "children": 0,
    "previous_cancellations": 1,
    "booking_changes": 0,
    "deposit_type": "No Deposit",
    "customer_type": "Transient",
    "market_segment": "Online TA",
    "required_car_parking_spaces": 0,
    "total_of_special_requests": 1,
    "adr": 95.5,
}


class CountingModel:
    classes_ = [0, 1]

    def __init__(self) -> None:
        self.predict_calls = 0

    def predict(self, frame) -> list[int]:
        self.predict_calls += 1
        return [1]

    def predict_proba(self, frame):
        return [[0.2, 0.8]]


def create_model_artifact(path: Path) -> Path:
    data = create_synthetic_dataset()
    x, y = prepare_training_data(data)
    pipeline = build_pipeline()
    pipeline.fit(x, y)
    joblib.dump(pipeline, path)
    return path


def test_predictor_loads_model_once(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"trusted-local-placeholder")
    model = CountingModel()
    calls = {"count": 0}

    def fake_load(path: Path) -> CountingModel:
        calls["count"] += 1
        return model

    monkeypatch.setattr("app.ml.predictor.joblib.load", fake_load)

    predictor = HotelCancellationPredictor(model_path)
    predictor.predict_one(VALID_FEATURES)
    predictor.predict_one(VALID_FEATURES)

    assert calls["count"] == 1
    assert model.predict_calls == 2


def test_predict_one_returns_expected_keys(tmp_path) -> None:
    predictor = HotelCancellationPredictor(create_model_artifact(tmp_path / "model.joblib"))

    result = predictor.predict_one(VALID_FEATURES)

    assert set(result) == {
        "prediction",
        "cancellation_probability",
        "risk_label",
        "model_name",
        "model_version",
        "features_used",
    }


def test_predict_one_probability_between_0_and_1(tmp_path) -> None:
    predictor = HotelCancellationPredictor(create_model_artifact(tmp_path / "model.joblib"))

    result = predictor.predict_one(VALID_FEATURES)

    assert 0.0 <= result["cancellation_probability"] <= 1.0


def test_predict_one_returns_low_medium_or_high_risk_label(tmp_path) -> None:
    predictor = HotelCancellationPredictor(create_model_artifact(tmp_path / "model.joblib"))

    result = predictor.predict_one(VALID_FEATURES)

    assert result["risk_label"] in {"low", "medium", "high"}


def test_missing_feature_raises_error(tmp_path) -> None:
    predictor = HotelCancellationPredictor(create_model_artifact(tmp_path / "model.joblib"))
    features = VALID_FEATURES.copy()
    features.pop("adr")

    with pytest.raises(InvalidFeaturePayloadError):
        predictor.predict_one(features)


def test_extra_feature_raises_error(tmp_path) -> None:
    predictor = HotelCancellationPredictor(create_model_artifact(tmp_path / "model.joblib"))
    features = VALID_FEATURES | {"unexpected": "value"}

    with pytest.raises(InvalidFeaturePayloadError):
        predictor.predict_one(features)


def test_leakage_feature_raises_error(tmp_path) -> None:
    predictor = HotelCancellationPredictor(create_model_artifact(tmp_path / "model.joblib"))
    features = VALID_FEATURES | {"reservation_status": "Canceled"}

    with pytest.raises(InvalidFeaturePayloadError):
        predictor.predict_one(features)


def test_numeric_feature_can_be_cast(tmp_path) -> None:
    predictor = HotelCancellationPredictor(create_model_artifact(tmp_path / "model.joblib"))
    features: dict[str, Any] = VALID_FEATURES | {"lead_time": "120", "adr": "95.5"}

    result = predictor.predict_one(features)

    assert result["prediction"] in {0, 1}


def test_invalid_numeric_feature_raises_error(tmp_path) -> None:
    predictor = HotelCancellationPredictor(create_model_artifact(tmp_path / "model.joblib"))
    features = VALID_FEATURES | {"lead_time": "not-a-number"}

    with pytest.raises(InvalidFeaturePayloadError):
        predictor.predict_one(features)


def test_model_not_found_raises_error(tmp_path) -> None:
    with pytest.raises(ModelNotFoundError):
        HotelCancellationPredictor(tmp_path / "missing.joblib")


def test_predict_many_returns_list(tmp_path) -> None:
    predictor = HotelCancellationPredictor(create_model_artifact(tmp_path / "model.joblib"))

    results = predictor.predict_many([VALID_FEATURES, VALID_FEATURES])

    assert isinstance(results, list)
    assert len(results) == 2


def test_predictor_uses_feature_contract_order(tmp_path) -> None:
    predictor = HotelCancellationPredictor(create_model_artifact(tmp_path / "model.joblib"))

    result = predictor.predict_one(dict(reversed(list(VALID_FEATURES.items()))))

    assert result["features_used"] == FEATURE_COLUMNS
