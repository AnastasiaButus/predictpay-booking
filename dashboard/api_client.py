import os
from typing import Any

import requests


DEFAULT_BACKEND_API_URL = "http://127.0.0.1:8000"


class APIError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BookingGuardAPIClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 15,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("BACKEND_API_URL") or DEFAULT_BACKEND_API_URL).rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def register(self, email: str, password: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        )

    def login(self, email: str, password: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    def logout(self, access_token: str, refresh_token: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/auth/logout",
            access_token=access_token,
            json={"refresh_token": refresh_token},
        )

    def get_me(self, access_token: str) -> dict[str, Any]:
        return self._request("GET", "/api/v1/users/me", access_token=access_token)

    def get_balance(self, access_token: str) -> dict[str, Any]:
        return self._request("GET", "/api/v1/billing/balance", access_token=access_token)

    def top_up(self, access_token: str, amount: int) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/billing/top-up",
            access_token=access_token,
            json={"amount": amount},
        )

    def get_transactions(
        self,
        access_token: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/billing/transactions",
            access_token=access_token,
            params={"limit": limit, "offset": offset},
        )

    def list_promocodes(self, access_token: str) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/promocodes", access_token=access_token)

    def activate_promocode(self, access_token: str, code: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/promocodes/activate",
            access_token=access_token,
            json={"code": code},
        )

    def activate_poincare_challenge(
        self,
        access_token: str,
        proof_url: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/promocodes/poincare-challenge",
            access_token=access_token,
            json={"proof_url": proof_url},
        )

    def create_prediction(
        self,
        access_token: str,
        features: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/predictions",
            access_token=access_token,
            json={"features": features},
        )

    def get_prediction(self, access_token: str, prediction_id: int) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/v1/predictions/{prediction_id}",
            access_token=access_token,
        )

    def get_prediction_history(
        self,
        access_token: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/predictions/history",
            access_token=access_token,
            params={"limit": limit, "offset": offset},
        )

    def _request(
        self,
        method: str,
        path: str,
        access_token: str | None = None,
        **kwargs: Any,
    ) -> Any:
        headers = kwargs.pop("headers", {})
        if access_token:
            headers.update(build_auth_headers(access_token))

        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise APIError("Backend is unavailable. Please try again later.") from exc

        if response.status_code >= 400:
            raise APIError(
                _extract_error_message(response),
                status_code=response.status_code,
            )

        if response.status_code == 204 or not response.content:
            return {}
        return response.json()


def build_auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Request failed with HTTP {response.status_code}."

    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        messages = []
        for item in detail:
            if isinstance(item, dict) and item.get("msg"):
                location = ".".join(str(part) for part in item.get("loc", []))
                messages.append(f"{location}: {item['msg']}" if location else item["msg"])
        if messages:
            return "; ".join(messages)
    return f"Request failed with HTTP {response.status_code}."
