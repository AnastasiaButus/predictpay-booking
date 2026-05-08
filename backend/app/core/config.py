from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "PredictPay BookingGuard"
    SERVICE_NAME: str = "predictpay-bookingguard"
    VERSION: str = "1.0.0"

    POSTGRES_DB: str = "predictpay"
    POSTGRES_USER: str = "predictpay"
    POSTGRES_PASSWORD: str = "predictpay"

    DATABASE_URL: str = "postgresql+psycopg://predictpay:predictpay@postgres:5432/predictpay"
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    JWT_SECRET_KEY: str = "change_me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BACKEND_CORS_ORIGINS: str = "http://localhost:8501"

    PREDICTION_COST: int = 10
    START_BALANCE: int = 100
    MODEL_PATH: str = "storage/models/hotel_cancellation_model.joblib"

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()
