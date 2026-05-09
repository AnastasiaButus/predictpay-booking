from datetime import datetime

from pydantic import AnyUrl, BaseModel, ConfigDict


class PromocodeActivateRequest(BaseModel):
    code: str


class PoincareChallengeRequest(BaseModel):
    proof_url: AnyUrl


class PromocodeActivationResponse(BaseModel):
    code: str
    credits_amount: int
    balance: int
    reserved_balance: int
    message: str


class PromocodeRead(BaseModel):
    code: str
    credits_amount: int
    max_activations: int
    current_activations: int
    expires_at: datetime | None
    is_active: bool
    description: str | None

    model_config = ConfigDict(from_attributes=True)
