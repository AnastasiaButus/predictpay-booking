from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    role: str
    plan: str
    balance: int
    reserved_balance: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


UserMe = UserRead
