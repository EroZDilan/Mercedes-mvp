from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database import get_db
from backend.schemas import LoginRequest, TokenResponse, RefreshRequest, AccessTokenResponse
from backend.services import auth_service
from backend.middleware.auth import get_current_user
from backend.middleware.rate_limiter import limiter
from backend import models

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.login_rate_limit)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    device = request.headers.get("user-agent", "")
    return auth_service.login(db, body.username, body.password, ip, device)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    return auth_service.refresh(db, body.refresh_token)


@router.post("/logout")
def logout(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    # We need the raw token to revoke by jti — extract via request
):
    # Revoke all non-revoked sessions for simplicity on explicit logout
    sessions = db.query(models.Session).filter(
        models.Session.user_id == current_user.id,
        models.Session.is_revoked == False,
    ).all()
    for s in sessions:
        s.is_revoked = True
    db.commit()
    return {"detail": "Sesión cerrada"}


@router.get("/me")
def me(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role.name,
        "warehouse_id": current_user.warehouse_id,
    }
