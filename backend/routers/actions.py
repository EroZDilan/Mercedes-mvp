"""Actions router — confirm and execute a pending chatbot action."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend import models
from backend.services.action_service import consume_action_token, execute_action

router = APIRouter(prefix="/actions", tags=["actions"])


class ConfirmRequest(BaseModel):
    action_token: str


@router.post("/confirm")
def confirm_action(
    body: ConfirmRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        action_data = consume_action_token(db, current_user, body.action_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        result_msg = execute_action(db, current_user, action_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al ejecutar la acción: {exc}",
        )

    return {"detail": result_msg}
