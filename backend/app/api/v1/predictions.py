from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import (
    BillingConsistencyError,
    InsufficientCreditsError,
    InvalidFeaturePayloadError,
    ModelLoadError,
    ModelMetadataNotFoundError,
    ModelNotFoundError,
    PredictionNotFoundError,
)
from app.models.user import User
from app.schemas.prediction import (
    PredictionCreateRequest,
    PredictionHistoryResponse,
    PredictionResponse,
)
from app.services.prediction_service import PredictionService, prediction_to_response


router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


@router.post("", response_model=PredictionResponse)
def create_prediction(
    payload: PredictionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _call_prediction_service(
        lambda: prediction_to_response(
            PredictionService(db).create_prediction_sync(
                current_user.id,
                payload.features.model_dump(),
            )
        )
    )


@router.get("/history", response_model=PredictionHistoryResponse)
def list_predictions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    predictions = PredictionService(db).list_predictions(
        current_user.id,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [prediction_to_response(prediction) for prediction in predictions],
        "limit": limit,
        "offset": offset,
    }


@router.get("/{prediction_id}", response_model=PredictionResponse)
def get_prediction(
    prediction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _call_prediction_service(
        lambda: prediction_to_response(
            PredictionService(db).get_prediction(current_user.id, prediction_id)
        )
    )


def _call_prediction_service(operation):
    try:
        return operation()
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(exc),
        ) from exc
    except PredictionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ModelMetadataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model artifact is missing. Run training first.",
        ) from exc
    except ModelLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except InvalidFeaturePayloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except BillingConsistencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction inference failed; reserved credits were refunded.",
        ) from exc
