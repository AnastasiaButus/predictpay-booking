import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.features import (
    CATEGORICAL_FEATURES,
    DEFAULT_METRICS_PATH,
    DEFAULT_MODEL_PATH,
    FEATURE_COLUMNS,
    LEAKAGE_COLUMNS,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
)


DEFAULT_DATA_PATH = Path("data/hotel_bookings.csv")
DEMO_QUALITY_NOTE = (
    "Synthetic demo dataset metrics are smoke-check only and must not be "
    "interpreted as real model quality."
)
REAL_DATA_QUALITY_NOTE = "Metrics computed on provided dataset split."


def create_synthetic_dataset() -> pd.DataFrame:
    rows = [
        ["City Hotel", 120, 2, 0, 1, 0, "No Deposit", "Transient", "Online TA", 0, 1, 95.5, 1],
        ["Resort Hotel", 14, 2, 1, 0, 1, "No Deposit", "Transient", "Direct", 1, 2, 132.0, 0],
        ["City Hotel", 220, 1, 0, 2, 0, "Non Refund", "Transient", "Online TA", 0, 0, 80.0, 1],
        ["Resort Hotel", 7, 2, 0, 0, 2, "No Deposit", "Contract", "Offline TA/TO", 0, 1, 110.0, 0],
        ["City Hotel", 45, 3, 0, 0, 0, "No Deposit", "Transient", "Groups", 0, 0, 150.0, 0],
        ["City Hotel", 180, 2, 0, 1, 0, "No Deposit", "Transient", "Online TA", 0, 1, 88.0, 1],
        ["Resort Hotel", 30, 2, 2, 0, 1, "No Deposit", "Transient-Party", "Direct", 1, 3, 180.0, 0],
        ["City Hotel", 300, 2, 0, 3, 0, "Non Refund", "Transient", "Online TA", 0, 0, 70.0, 1],
        ["Resort Hotel", 21, 1, 0, 0, 1, "No Deposit", "Contract", "Corporate", 0, 2, 99.0, 0],
        ["City Hotel", 160, 2, 0, 1, 0, "No Deposit", "Transient", "Groups", 0, 0, 105.0, 1],
        ["Resort Hotel", 5, 2, 0, 0, 3, "No Deposit", "Transient", "Direct", 1, 4, 210.0, 0],
        ["City Hotel", 250, 1, 0, 2, 0, "Non Refund", "Transient", "Online TA", 0, 0, 75.0, 1],
    ]
    columns = FEATURE_COLUMNS + [TARGET_COLUMN]
    data = pd.DataFrame(rows, columns=columns)
    data["reservation_status"] = data[TARGET_COLUMN].map({0: "Check-Out", 1: "Canceled"})
    data["reservation_status_date"] = "2017-01-01"
    return data


def load_training_data(
    data_path: Path | str = DEFAULT_DATA_PATH,
) -> tuple[pd.DataFrame, str, bool]:
    path = Path(data_path)
    if path.exists():
        return pd.read_csv(path), str(path), False
    return create_synthetic_dataset(), "synthetic demo dataset", True


def build_pipeline(random_state: int = 42) -> Pipeline:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
            ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ]
    )
    classifier = RandomForestClassifier(
        n_estimators=50,
        max_depth=5,
        min_samples_leaf=1,
        random_state=random_state,
    )
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )


def prepare_training_data(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    missing_columns = [
        column
        for column in [*FEATURE_COLUMNS, TARGET_COLUMN]
        if column not in data.columns
    ]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    return data[FEATURE_COLUMNS].copy(), data[TARGET_COLUMN].astype(int)


def can_stratify(target: pd.Series) -> bool:
    value_counts = target.value_counts()
    return len(value_counts) > 1 and bool((value_counts >= 2).all())


def train_model(
    data_path: Path | str = DEFAULT_DATA_PATH,
    model_path: Path | str = DEFAULT_MODEL_PATH,
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
    random_state: int = 42,
) -> dict[str, Any]:
    data, source, is_demo_dataset = load_training_data(data_path)
    x, y = prepare_training_data(data)
    stratify = y if can_stratify(y) else None

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.25,
        random_state=random_state,
        stratify=stratify,
    )

    pipeline = build_pipeline(random_state=random_state)
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)

    roc_auc_warning = None
    roc_auc = None
    if len(set(y_test)) > 1 and hasattr(pipeline, "predict_proba"):
        probabilities = pipeline.predict_proba(x_test)[:, 1]
        roc_auc = float(roc_auc_score(y_test, probabilities))
    else:
        roc_auc_warning = "roc_auc is null because the test set has one class."

    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "roc_auc": roc_auc,
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "n_train": int(len(x_train)),
        "n_test": int(len(x_test)),
        "features": FEATURE_COLUMNS,
        "leakage_excluded": LEAKAGE_COLUMNS,
        "model_type": "sklearn_pipeline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "is_demo_dataset": is_demo_dataset,
        "quality_note": (
            DEMO_QUALITY_NOTE if is_demo_dataset else REAL_DATA_QUALITY_NOTE
        ),
    }
    if roc_auc_warning is not None:
        metrics["warning"] = roc_auc_warning

    model_path = Path(model_path)
    metrics_path = Path(metrics_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(pipeline, model_path)
    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train hotel cancellation model.")
    parser.add_argument("--data-path", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--metrics-path", default=DEFAULT_METRICS_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics = train_model(
        data_path=args.data_path,
        model_path=args.model_path,
        metrics_path=args.metrics_path,
    )
    print(f"source: {metrics['source']}")
    print(f"model path: {args.model_path}")
    print(f"metrics path: {args.metrics_path}")
    print(f"is demo dataset: {metrics['is_demo_dataset']}")
    print(f"quality note: {metrics['quality_note']}")
    print(f"accuracy: {metrics['accuracy']:.4f}")
    print(f"f1: {metrics['f1']:.4f}")
    print(f"roc_auc: {metrics['roc_auc']}")
    print(f"feature count: {len(metrics['features'])}")
    print(f"leakage excluded columns: {', '.join(metrics['leakage_excluded'])}")


if __name__ == "__main__":
    main()
