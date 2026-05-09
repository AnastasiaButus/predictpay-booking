import json

import joblib
from sklearn.pipeline import Pipeline

from app.ml.features import FEATURE_COLUMNS, LEAKAGE_COLUMNS, TARGET_COLUMN
from app.ml.train_model import (
    build_pipeline,
    create_synthetic_dataset,
    prepare_training_data,
    train_model,
)


REQUIRED_METRIC_KEYS = {
    "accuracy",
    "roc_auc",
    "f1",
    "n_train",
    "n_test",
    "features",
    "leakage_excluded",
    "model_type",
    "created_at",
    "is_demo_dataset",
    "quality_note",
}


def test_synthetic_dataset_contains_required_columns() -> None:
    data = create_synthetic_dataset()

    assert set([*FEATURE_COLUMNS, TARGET_COLUMN]).issubset(data.columns)


def test_build_pipeline_returns_sklearn_pipeline() -> None:
    assert isinstance(build_pipeline(), Pipeline)


def test_pipeline_can_fit_small_synthetic_dataset() -> None:
    data = create_synthetic_dataset()
    x, y = prepare_training_data(data)
    pipeline = build_pipeline()

    pipeline.fit(x, y)

    assert len(pipeline.predict(x.head(2))) == 2


def test_train_model_writes_artifact_and_metrics_to_temp_dir(tmp_path) -> None:
    model_path = tmp_path / "model.joblib"
    metrics_path = tmp_path / "metrics.json"

    train_model(model_path=model_path, metrics_path=metrics_path)

    assert model_path.exists()
    assert metrics_path.exists()
    assert isinstance(joblib.load(model_path), Pipeline)


def test_metrics_json_contains_required_keys(tmp_path) -> None:
    metrics_path = tmp_path / "metrics.json"

    train_model(model_path=tmp_path / "model.joblib", metrics_path=metrics_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert REQUIRED_METRIC_KEYS.issubset(metrics)


def test_synthetic_fallback_sets_is_demo_dataset_true(tmp_path) -> None:
    metrics_path = tmp_path / "metrics.json"

    train_model(
        data_path=tmp_path / "missing.csv",
        model_path=tmp_path / "model.joblib",
        metrics_path=metrics_path,
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert metrics["source"] == "synthetic demo dataset"
    assert metrics["is_demo_dataset"] is True
    assert "smoke-check only" in metrics["quality_note"]


def test_real_csv_path_sets_is_demo_dataset_false(tmp_path) -> None:
    data = create_synthetic_dataset()
    csv_path = tmp_path / "hotel_bookings.csv"
    metrics_path = tmp_path / "metrics.json"
    data.to_csv(csv_path, index=False)

    train_model(
        data_path=csv_path,
        model_path=tmp_path / "model.joblib",
        metrics_path=metrics_path,
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert metrics["source"] == str(csv_path)
    assert metrics["is_demo_dataset"] is False
    assert metrics["quality_note"] == "Metrics computed on provided dataset split."


def test_no_leakage_columns_used_in_training_features() -> None:
    data = create_synthetic_dataset()
    x, _ = prepare_training_data(data)

    assert list(x.columns) == FEATURE_COLUMNS
    assert set(LEAKAGE_COLUMNS).isdisjoint(x.columns)
