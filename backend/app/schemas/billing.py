from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BalanceResponse(BaseModel):
    balance: int
    reserved_balance: int

    model_config = ConfigDict(from_attributes=True)


class TopUpRequest(BaseModel):
    amount: int = Field(gt=0)


class TransactionRead(BaseModel):
    id: int
    amount: int
    transaction_type: str
    status: str
    reason: str | None
    prediction_id: int | None
    promocode_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionsListResponse(BaseModel):
    items: list[TransactionRead]
    limit: int
    offset: int
