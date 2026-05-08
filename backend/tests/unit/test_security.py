from datetime import timedelta

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_token,
    verify_password,
)


def test_hash_password_not_equal_plain_password() -> None:
    password = "StrongPassword123!"

    hashed_password = get_password_hash(password)

    assert hashed_password != password


def test_verify_password_success() -> None:
    password = "StrongPassword123!"
    hashed_password = get_password_hash(password)

    assert verify_password(password, hashed_password) is True


def test_verify_password_failure() -> None:
    hashed_password = get_password_hash("StrongPassword123!")

    assert verify_password("WrongPassword123!", hashed_password) is False


def test_access_token_contains_sub_role_type() -> None:
    token = create_access_token(
        user_id=123,
        role="admin",
        expires_delta=timedelta(minutes=5),
    )

    payload = decode_token(token)

    assert payload["sub"] == "123"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_refresh_token_contains_sub_type() -> None:
    token = create_refresh_token(user_id=123, expires_delta=timedelta(days=1))

    payload = decode_token(token)

    assert payload["sub"] == "123"
    assert payload["type"] == "refresh"


def test_hash_token_is_sha256_like_and_stable() -> None:
    token = "refresh-token-value"

    token_hash = hash_token(token)

    assert len(token_hash) == 64
    assert token_hash == hash_token(token)
    assert token_hash != token
