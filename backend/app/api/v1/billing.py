from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import BillingConsistencyError, InsufficientCreditsError
from app.models.user import User
from app.schemas.billing import (
    BalanceResponse,
    TopUpRequest,
    TransactionsListResponse,
)
from app.services.billing_service import BillingService


router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/balance", response_model=BalanceResponse)
def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return _call_billing_service(
        lambda: BillingService(db).get_balance(current_user.id)
    )


@router.post("/top-up", response_model=BalanceResponse)
def top_up(
    payload: TopUpRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return _call_billing_service(
        lambda: BillingService(db).top_up(current_user.id, payload.amount)
    )


@router.get("/transactions", response_model=TransactionsListResponse)
def list_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    transactions = _call_billing_service(
        lambda: BillingService(db).list_transactions(
            current_user.id, limit=limit, offset=offset
        )
    )
    return {"items": transactions, "limit": limit, "offset": offset}


def _call_billing_service(operation):
    try:
        return operation()
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(exc),
        ) from exc
    except BillingConsistencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
