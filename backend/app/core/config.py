from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "PredictPay BookingGuard"
    SERVICE_NAME: str = "predictpay-bookingguard"
    VERSION: str = "1.0.0"

    DATABASE_URL: str = "postgresql+psycopg://predictpay:predictpay@localhost:5432/predictpay_bookingguard"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    JWT_SECRET_KEY: str = "change-me-demo-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8501"]
    )

    PREDICTION_COST: int = 1
    START_BALANCE: int = 10
    MODEL_PATH: str = "storage/models/model.pkl"

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()
