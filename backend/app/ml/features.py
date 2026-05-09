FEATURE_COLUMNS = [
    "hotel",
    "lead_time",
    "adults",
    "children",
    "previous_cancellations",
    "booking_changes",
    "deposit_type",
    "customer_type",
    "market_segment",
    "required_car_parking_spaces",
    "total_of_special_requests",
    "adr",
]

CATEGORICAL_FEATURES = [
    "hotel",
    "deposit_type",
    "customer_type",
    "market_segment",
]

NUMERIC_FEATURES = [
    "lead_time",
    "adults",
    "children",
    "previous_cancellations",
    "booking_changes",
    "required_car_parking_spaces",
    "total_of_special_requests",
    "adr",
]

TARGET_COLUMN = "is_canceled"

LEAKAGE_COLUMNS = [
    "reservation_status",
    "reservation_status_date",
]

DEFAULT_MODEL_PATH = "storage/models/hotel_cancellation_model.joblib"
DEFAULT_METRICS_PATH = "storage/models/hotel_cancellation_model_metrics.json"
