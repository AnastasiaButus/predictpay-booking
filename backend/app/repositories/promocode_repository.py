from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.promocode import Promocode
from app.models.promocode_activation import PromocodeActivation


class PromocodeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_code(self, code: str) -> Promocode | None:
        return self.db.scalar(select(Promocode).where(Promocode.code == code))

    def get_by_code_for_update(self, code: str) -> Promocode | None:
        return self.db.scalar(
            select(Promocode).where(Promocode.code == code).with_for_update()
        )

    def get_activation(
        self,
        user_id: int,
        promocode_id: int,
    ) -> PromocodeActivation | None:
        return self.db.scalar(
            select(PromocodeActivation).where(
                PromocodeActivation.user_id == user_id,
                PromocodeActivation.promocode_id == promocode_id,
            )
        )

    def create_activation(
        self,
        user_id: int,
        promocode_id: int,
    ) -> PromocodeActivation:
        activation = PromocodeActivation(user_id=user_id, promocode_id=promocode_id)
        self.db.add(activation)
        self.db.flush()
        return activation

    def increment_current_activations(self, promocode: Promocode) -> Promocode:
        promocode.current_activations += 1
        self.db.add(promocode)
        self.db.flush()
        return promocode

    def list_active_promocodes(self) -> list[Promocode]:
        return list(
            self.db.scalars(
                select(Promocode)
                .where(Promocode.is_active.is_(True))
                .order_by(Promocode.code)
            )
        )
