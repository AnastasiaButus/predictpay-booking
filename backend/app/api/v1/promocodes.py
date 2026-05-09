from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import (
    BillingConsistencyError,
    InvalidChallengeSubmissionError,
    PromocodeActivationLimitError,
    PromocodeAlreadyActivatedError,
    PromocodeExpiredError,
    PromocodeInactiveError,
    PromocodeNotFoundError,
)
from app.models.user import User
from app.schemas.promocode import (
    PoincareChallengeRequest,
    PromocodeActivateRequest,
    PromocodeActivationResponse,
    PromocodeRead,
)
from app.services.promocode_service import PromocodeService


router = APIRouter(prefix="/api/v1/promocodes", tags=["promocodes"])


@router.get("", response_model=list[PromocodeRead])
def list_promocodes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    return _call_promocode_service(lambda: PromocodeService(db).list_promocodes())


@router.post("/activate", response_model=PromocodeActivationResponse)
def activate_promocode(
    payload: PromocodeActivateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _call_promocode_service(
        lambda: PromocodeService(db).activate_promocode(
            current_user.id,
            payload.code,
        )
    )


@router.post("/poincare-challenge", response_model=PromocodeActivationResponse)
def activate_poincare_challenge(
    payload: PoincareChallengeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _call_promocode_service(
        lambda: PromocodeService(db).activate_poincare_challenge(
            current_user.id,
            str(payload.proof_url),
        )
    )


def _call_promocode_service(operation):
    try:
        return operation()
    except PromocodeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        PromocodeInactiveError,
        PromocodeExpiredError,
        PromocodeActivationLimitError,
        PromocodeAlreadyActivatedError,
        BillingConsistencyError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidChallengeSubmissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
