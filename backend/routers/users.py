"""Users router — admin-only CRUD for user management."""
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.middleware.auth import require_role
from backend.services.auth_service import hash_password, force_logout_user
from backend import models, schemas

router = APIRouter(prefix="/users", tags=["users"])

_ADMIN = require_role("admin")


def _validate_password(password: str):
    if len(password) < 8:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Contraseña: mínimo 8 caracteres")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Contraseña: al menos una mayúscula")
    if not re.search(r"\d", password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Contraseña: al menos un número")
    if not re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~]', password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Contraseña: al menos un carácter especial")


def _user_to_dict(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.name,
        "role_id": user.role_id,
        "warehouse_id": user.warehouse_id,
        "is_active": user.is_active,
        "is_locked": user.is_locked,
        "failed_attempts": user.failed_attempts,
        "created_at": user.created_at,
        "last_login": user.last_login,
    }


@router.get("")
def list_users(
    _admin=Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    users = db.query(models.User).all()
    return [_user_to_dict(u) for u in users]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: schemas.UserCreateRequest,
    _admin=Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    _validate_password(body.password)

    existing = db.query(models.User).filter_by(username=body.username).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username ya existe")

    role = db.query(models.Role).filter_by(id=body.role_id).first()
    if not role:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rol no encontrado")

    if body.warehouse_id is not None:
        wh = db.query(models.Warehouse).filter_by(id=body.warehouse_id).first()
        if not wh:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Almacén no encontrado")

    user = models.User(
        username=body.username,
        password_hash=hash_password(body.password),
        role_id=body.role_id,
        warehouse_id=body.warehouse_id,
        full_name=body.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_to_dict(user)


@router.get("/{user_id}")
def get_user(
    user_id: int,
    _admin=Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return _user_to_dict(user)


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: schemas.UserUpdateRequest,
    _admin=Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")

    if body.role_id is not None:
        role = db.query(models.Role).filter_by(id=body.role_id).first()
        if not role:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rol no encontrado")
        user.role_id = body.role_id

    if body.warehouse_id is not None:
        wh = db.query(models.Warehouse).filter_by(id=body.warehouse_id).first()
        if not wh:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Almacén no encontrado")
        user.warehouse_id = body.warehouse_id

    if body.full_name is not None:
        user.full_name = body.full_name

    if body.is_active is not None:
        user.is_active = body.is_active

    db.commit()
    db.refresh(user)
    return _user_to_dict(user)


@router.post("/{user_id}/unlock")
def unlock_user(
    user_id: int,
    admin: models.User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    user.is_locked = False
    user.failed_attempts = 0
    db.commit()
    return {"detail": f"Cuenta de '{user.username}' desbloqueada"}


@router.post("/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    admin: models.User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    user.is_active = False
    db.commit()
    return {"detail": f"Cuenta de '{user.username}' desactivada"}


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    body: schemas.PasswordResetRequest,
    _admin=Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    _validate_password(body.new_password)
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"detail": f"Contraseña de '{user.username}' actualizada"}


@router.post("/{user_id}/force-logout")
def force_logout(
    user_id: int,
    admin: models.User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    revoked = force_logout_user(db, user_id, admin.id)
    return {"detail": f"{revoked} sesión(es) revocada(s) para '{user.username}'"}
