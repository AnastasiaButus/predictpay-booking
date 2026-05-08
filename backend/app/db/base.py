from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.ml_model import MLModel  # noqa: E402,F401
from app.models.prediction import Prediction  # noqa: E402,F401
from app.models.promocode import Promocode  # noqa: E402,F401
from app.models.promocode_activation import PromocodeActivation  # noqa: E402,F401
from app.models.refresh_token import RefreshToken  # noqa: E402,F401
from app.models.transaction import Transaction  # noqa: E402,F401
from app.models.user import User  # noqa: E402,F401
