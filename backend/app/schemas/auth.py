from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LogoutRequest(BaseModel):
    refresh_token: str
