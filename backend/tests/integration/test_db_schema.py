import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.base import Base  # noqa: E402
from app.models import (  # noqa: E402,F401
    MLModel,
    Prediction,
    Promocode,
    PromocodeActivation,
    RefreshToken,
    Transaction,
    User,
)


EXPECTED_TABLES = {
    "users",
    "refresh_tokens",
    "ml_models",
    "predictions",
    "transactions",
    "promocodes",
    "promocode_activations",
}


def test_metadata_contains_expected_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
