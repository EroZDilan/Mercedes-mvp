from datetime import datetime, UTC, timedelta
from uuid import uuid4
import bcrypt
from jose import JWTError, jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.config import settings
from backend import models


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _create_token(data: dict, expires_delta: timedelta) -> tuple[str, str]:
    jti = str(uuid4())
    payload = {**data, "jti": jti, "exp": datetime.now(UTC) + expires_delta}
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def create_access_token(user_id: int, role: str) -> tuple[str, str]:
    return _create_token(
        {"sub": str(user_id), "role": role, "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: int) -> tuple[str, str]:
    return _create_token(
        {"sub": str(user_id), "type": "refresh"},
        timedelta(hours=settings.refresh_token_expire_hours),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")


def _write_audit(db: Session, user_id: int | None, action: str, detail: str, ip: str):
    db.add(models.AuditLog(user_id=user_id, action=action, detail=detail, ip_address=ip))


def login(db: Session, username: str, password: str, ip: str, device_info: str = "") -> dict:
    user = db.query(models.User).filter(models.User.username == username).first()

    if not user:
        _write_audit(db, None, "LOGIN_FAILED", f"username={username} not found", ip)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    if not user.is_active:
        _write_audit(db, user.id, "LOGIN_FAILED", "account inactive", ip)
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta desactivada")

    if user.is_locked:
        _write_audit(db, user.id, "LOGIN_FAILED", "account locked", ip)
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta bloqueada. Contacta al administrador")

    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.max_login_attempts:
            user.is_locked = True
            _write_audit(db, user.id, "ACCOUNT_LOCKED", f"locked after {user.failed_attempts} failed attempts", ip)
            # Notify admin
            admin = db.query(models.User).join(models.Role).filter(models.Role.name == "admin").first()
            if admin:
                db.add(models.Notification(
                    recipient_user_id=admin.id,
                    type="account_locked",
                    message=f"Cuenta '{username}' bloqueada por {user.failed_attempts} intentos fallidos desde {ip}",
                    related_user_id=user.id,
                ))
        else:
            _write_audit(db, user.id, "LOGIN_FAILED", f"wrong password, attempt {user.failed_attempts}", ip)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    # Success
    user.failed_attempts = 0
    user.last_login = datetime.now(UTC)

    access_token, access_jti = create_access_token(user.id, user.role.name)
    refresh_token, refresh_jti = create_refresh_token(user.id)

    access_expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    refresh_expires = datetime.now(UTC) + timedelta(hours=settings.refresh_token_expire_hours)

    db.add(models.Session(
        user_id=user.id, jti=access_jti, device_info=device_info,
        ip_address=ip, expires_at=access_expires,
    ))
    db.add(models.Session(
        user_id=user.id, jti=refresh_jti, device_info=device_info,
        ip_address=ip, expires_at=refresh_expires,
    ))
    _write_audit(db, user.id, "LOGIN_SUCCESS", f"ip={ip}", ip)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role.name,
            "warehouse_id": user.warehouse_id,
        },
    }


def refresh(db: Session, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    jti = payload.get("jti")
    session = db.query(models.Session).filter(models.Session.jti == jti).first()
    if not session or session.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión revocada")

    user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
    if not user or not user.is_active or user.is_locked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no disponible")

    access_token, access_jti = create_access_token(user.id, user.role.name)
    access_expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    db.add(models.Session(
        user_id=user.id, jti=access_jti,
        device_info=session.device_info, ip_address=session.ip_address,
        expires_at=access_expires,
    ))
    db.commit()
    return {"access_token": access_token, "token_type": "bearer"}


def logout(db: Session, jti: str):
    session = db.query(models.Session).filter(models.Session.jti == jti).first()
    if session:
        session.is_revoked = True
        db.commit()


def force_logout_user(db: Session, target_user_id: int, admin_id: int):
    sessions = db.query(models.Session).filter(
        models.Session.user_id == target_user_id,
        models.Session.is_revoked == False,
    ).all()
    for s in sessions:
        s.is_revoked = True
    _write_audit(db, admin_id, "FORCE_LOGOUT", f"forced logout of user_id={target_user_id}", "")
    db.commit()
    return len(sessions)
