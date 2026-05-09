from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.core.exceptions import (
    InvalidFeaturePayloadError,
    ModelLoadError,
    ModelNotFoundError,
)
from app.ml.features import (
    CATEGORICAL_FEATURES,
    DEFAULT_MODEL_PATH,
    FEATURE_COLUMNS,
    LEAKAGE_COLUMNS,
    NUMERIC_FEATURES,
)


MODEL_NAME = "hotel_cancellation_model"
MODEL_VERSION = "1.0.0"


class HotelCancellationPredictor:
    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH) -> None:
        self.model_path = Path(model_path)
        self.model = self.load_model()

    def load_model(self) -> Any:
        if not self.model_path.exists():
            raise ModelNotFoundError(f"Model artifact not found: {self.model_path}")

        try:
            model = joblib.load(self.model_path)
        except Exception as exc:
            raise ModelLoadError(f"Failed to load model artifact: {self.model_path}") from exc

        if not hasattr(model, "predict"):
            raise ModelLoadError("Loaded model does not provide predict().")

        return model

    def predict_one(self, features: dict[str, Any]) -> dict[str, Any]:
        validated_features = self._validate_features(features)
        frame = pd.DataFrame([validated_features], columns=FEATURE_COLUMNS)
        prediction = int(self.model.predict(frame)[0])
        probability = self._predict_cancellation_probability(frame, prediction)

        return {
            "prediction": prediction,
            "cancellation_probability": probability,
            "risk_label": self._risk_label(probability),
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "features_used": FEATURE_COLUMNS,
        }

    def predict_many(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.predict_one(item) for item in items]

    def _validate_features(self, features: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(features, dict):
            raise InvalidFeaturePayloadError("Features payload must be a dictionary.")

        leakage_present = sorted(set(features) & set(LEAKAGE_COLUMNS))
        if leakage_present:
            raise InvalidFeaturePayloadError(
                f"Leakage columns are not allowed: {leakage_present}"
            )

        missing = [column for column in FEATURE_COLUMNS if column not in features]
        if missing:
            raise InvalidFeaturePayloadError(f"Missing required features: {missing}")

        extra = sorted(set(features) - set(FEATURE_COLUMNS))
        if extra:
            raise InvalidFeaturePayloadError(f"Unexpected extra features: {extra}")

        validated: dict[str, Any] = {}
        for column in NUMERIC_FEATURES:
            try:
                validated[column] = float(features[column])
            except (TypeError, ValueError) as exc:
                raise InvalidFeaturePayloadError(
                    f"Feature '{column}' must be numeric."
                ) from exc

        for column in CATEGORICAL_FEATURES:
            value = features[column]
            if value is None:
                raise InvalidFeaturePayloadError(
                    f"Feature '{column}' must not be null."
                )
            validated[column] = str(value)

        return {column: validated[column] for column in FEATURE_COLUMNS}

    def _predict_cancellation_probability(
        self,
        frame: pd.DataFrame,
        prediction: int,
    ) -> float:
        if not hasattr(self.model, "predict_proba"):
            return float(prediction)

        probabilities = self.model.predict_proba(frame)
        classes = getattr(self.model, "classes_", None)
        if classes is not None:
            class_list = list(classes)
            if 1 in class_list:
                return float(probabilities[0][class_list.index(1)])

        if probabilities.shape[1] >= 2:
            return float(probabilities[0][1])

        return float(prediction)

    def _risk_label(self, probability: float) -> str:
        if probability < 0.35:
            return "low"
        if probability < 0.65:
            return "medium"
        return "high"
