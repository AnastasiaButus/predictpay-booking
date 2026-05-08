VALID_BOOKING_PAYLOAD = {
    "model_id": 1,
    "features": {
        "hotel": "City Hotel",
        "lead_time": 120,
        "adults": 2,
        "children": 0,
        "previous_cancellations": 1,
        "booking_changes": 0,
        "deposit_type": "No Deposit",
        "customer_type": "Transient",
        "market_segment": "Online TA",
        "required_car_parking_spaces": 0,
        "total_of_special_requests": 1,
        "adr": 95.5,
    },
}

INVALID_BOOKING_PAYLOAD = {
    "model_id": 1,
    "features": {
        "hotel": "City Hotel",
        "lead_time": 120,
        "adults": 2,
        "children": 0,
        "previous_cancellations": 1,
        "booking_changes": 0,
        "deposit_type": "No Deposit",
        "customer_type": "Transient",
        "market_segment": "Online TA",
        "required_car_parking_spaces": 0,
        "total_of_special_requests": 1,
        "adr": -1,
    },
}
