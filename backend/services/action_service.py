"""Action service — token lifecycle, confirmation summaries, and execution."""
import json
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from sqlalchemy.orm import Session

from backend import models
from backend.config import settings
from backend.services.stock_service import _find_superior
from backend.services import inventree_service

VALID_STATUSES = {"disponible", "reservado", "en_reparacion", "dado_de_baja"}


# ── Token lifecycle ───────────────────────────────────────────────────────────

def create_action_token(db: Session, user_id: int, action_data: dict) -> str:
    token = str(uuid.uuid4())
    expires = datetime.now(UTC) + timedelta(seconds=settings.action_token_ttl_seconds)
    db.add(models.ActionToken(
        token=token,
        user_id=user_id,
        action_data=json.dumps(action_data, ensure_ascii=False),
        expires_at=expires,
    ))
    db.commit()
    return token


def consume_action_token(db: Session, user: models.User, token_str: str) -> dict:
    """Validate and mark token as used. Returns action_data or raises ValueError."""
    now = datetime.now(UTC)
    token = db.query(models.ActionToken).filter_by(token=token_str, used=False).first()

    if not token:
        raise ValueError("Token inválido o ya utilizado.")
    if token.user_id != user.id:
        raise ValueError("Este token no pertenece a tu sesión.")

    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < now:
        raise ValueError("El token ha expirado (60 s). Solicita la acción de nuevo.")

    token.used = True
    db.flush()
    return json.loads(token.action_data)


# ── Confirmation summaries ────────────────────────────────────────────────────

def build_confirmation_summary(db: Session, action_data: dict) -> tuple[str, bool]:
    """Build human-readable summary from real DB data.

    Returns (text, is_valid). is_valid=False means the action is not feasible.
    """
    action_type = action_data.get("action_type", "")
    params = action_data.get("params", {})
    try:
        dispatch = {
            "transfer": _summary_transfer,
            "status_change": _summary_status_change,
            "create_product": _summary_create_product,
            "edit_product": _summary_edit_product,
            "delete_product": _summary_delete_product,
            "create_user": _summary_create_user,
            "deactivate_user": _summary_deactivate_user,
            "reset_password": _summary_reset_password,
        }
        fn = dispatch.get(action_type)
        if not fn:
            return f"Tipo de acción desconocido: {action_type}", False
        return fn(db, params)
    except Exception as exc:
        return f"Error al preparar la acción: {exc}", False


def _summary_transfer(db, params):
    from_code = params.get("from_warehouse", "")
    to_code = params.get("to_warehouse", "")
    product_code = params.get("product_code", "")
    quantity = int(params.get("quantity", 0))

    from_wh = db.query(models.Warehouse).filter_by(code=from_code).first()
    to_wh = db.query(models.Warehouse).filter_by(code=to_code).first()
    if not from_wh:
        return f"Almacén origen '{from_code}' no encontrado.", False
    if not to_wh:
        return f"Almacén destino '{to_code}' no encontrado.", False

    stock = db.query(models.Stock).filter_by(
        warehouse_id=from_wh.id, product_code=product_code
    ).first()
    if not stock:
        return f"Producto '{product_code}' no encontrado en {from_wh.name}.", False
    if stock.quantity < quantity:
        return (
            f"Stock insuficiente: {stock.product_name} tiene {stock.quantity} "
            f"unidades en {from_wh.name}, pero se piden {quantity}.",
            False,
        )

    remaining = stock.quantity - quantity
    return (
        f"Vas a transferir **{quantity} {stock.unit}** de **{stock.product_name}** "
        f"({product_code}) del {from_wh.name} al {to_wh.name}.\n"
        f"Stock actual en {from_wh.name}: {stock.quantity} → quedarán {remaining} unidades.",
        True,
    )


def _summary_status_change(db, params):
    identifier = params.get("product_identifier", "")
    wh_code = params.get("warehouse_code", "")
    new_status = params.get("new_status", "")

    if new_status not in VALID_STATUSES:
        return f"Estado inválido: '{new_status}'.", False

    wh = db.query(models.Warehouse).filter_by(code=wh_code).first()
    if not wh:
        return f"Almacén '{wh_code}' no encontrado.", False

    stock = db.query(models.Stock).filter_by(warehouse_id=wh.id, product_code=identifier).first()
    if stock:
        return (
            f"Vas a cambiar el estado de **{stock.product_name}** ({identifier}) "
            f"en {wh.name} de '{stock.status}' a **'{new_status}'**.",
            True,
        )

    serial = db.query(models.StockSerial).filter_by(
        warehouse_id=wh.id, serial_number=identifier
    ).first()
    if serial:
        return (
            f"Vas a cambiar el estado de **{serial.product_name}** (SN: {identifier}) "
            f"en {wh.name} de '{serial.status}' a **'{new_status}'**.",
            True,
        )

    return f"Producto '{identifier}' no encontrado en {wh.name}.", False


def _summary_create_product(db, params):
    wh_code = params.get("warehouse_code", "")
    product_code = params.get("product_code", "")

    wh = db.query(models.Warehouse).filter_by(code=wh_code).first()
    if not wh:
        return f"Almacén '{wh_code}' no encontrado.", False
    if db.query(models.Stock).filter_by(warehouse_id=wh.id, product_code=product_code).first():
        return f"El producto '{product_code}' ya existe en {wh.name}.", False

    return (
        f"Vas a crear **{params.get('product_name')}** ({product_code}) en {wh.name}.\n"
        f"Categoría: {params.get('category')} | Cantidad inicial: {params.get('quantity')} "
        f"{params.get('unit', 'unidad')} | Stock mínimo: {params.get('min_quantity')} | "
        f"Ubicación: {params.get('location') or 'Sin especificar'}",
        True,
    )


def _summary_edit_product(db, params):
    wh_code = params.get("warehouse_code", "")
    product_code = params.get("product_code", "")

    wh = db.query(models.Warehouse).filter_by(code=wh_code).first()
    if not wh:
        return f"Almacén '{wh_code}' no encontrado.", False

    stock = db.query(models.Stock).filter_by(warehouse_id=wh.id, product_code=product_code).first()
    if not stock:
        return f"Producto '{product_code}' no encontrado en {wh.name}.", False

    field = params.get("field", "")
    old_value = str(getattr(stock, field, ""))
    return (
        f"Vas a editar **{stock.product_name}** ({product_code}) en {wh.name}.\n"
        f"Campo: {field} | Valor actual: '{old_value}' → Nuevo valor: '{params.get('new_value')}'",
        True,
    )


def _summary_delete_product(db, params):
    wh_code = params.get("warehouse_code", "")
    product_code = params.get("product_code", "")

    wh = db.query(models.Warehouse).filter_by(code=wh_code).first()
    if not wh:
        return f"Almacén '{wh_code}' no encontrado.", False

    stock = db.query(models.Stock).filter_by(warehouse_id=wh.id, product_code=product_code).first()
    if not stock:
        return f"Producto '{product_code}' no encontrado en {wh.name}.", False

    return (
        f"Vas a **dar de baja** el producto **{stock.product_name}** ({product_code}) "
        f"de {wh.name}.\nStock actual: {stock.quantity} unidades. Esta acción no se puede deshacer.",
        True,
    )


def _summary_create_user(db, params):
    username = params.get("username", "")
    if db.query(models.User).filter_by(username=username).first():
        return f"El usuario '{username}' ya existe.", False

    wh_info = ""
    if params.get("warehouse_code"):
        wh = db.query(models.Warehouse).filter_by(code=params["warehouse_code"]).first()
        wh_info = f" | Almacén: {wh.name if wh else params['warehouse_code']}"

    temp_pwd = _gen_temp_password()
    params["_temp_password"] = temp_pwd

    return (
        f"Vas a crear el usuario **{username}** ({params.get('full_name')}).\n"
        f"Rol: {params.get('role_name')}{wh_info} | Contraseña temporal: **{temp_pwd}**",
        True,
    )


def _summary_deactivate_user(db, params):
    username = params.get("username", "")
    target = db.query(models.User).filter_by(username=username).first()
    if not target:
        return f"Usuario '{username}' no encontrado.", False
    if not target.is_active:
        return f"El usuario '{username}' ya está desactivado.", False
    return (
        f"Vas a **desactivar** al usuario **{username}** ({target.full_name}).\n"
        f"No podrá iniciar sesión hasta que un admin lo reactive.",
        True,
    )


def _summary_reset_password(db, params):
    username = params.get("username", "")
    target = db.query(models.User).filter_by(username=username).first()
    if not target:
        return f"Usuario '{username}' no encontrado.", False
    return (
        f"Vas a resetear la contraseña de **{username}** ({target.full_name}).\n"
        f"Nueva contraseña: **{params.get('new_password')}**",
        True,
    )


def _gen_temp_password() -> str:
    chars = string.ascii_letters + string.digits + "!@#$"
    while True:
        pwd = "".join(secrets.choice(chars) for _ in range(10))
        if any(c.isupper() for c in pwd) and any(c.isdigit() for c in pwd) and any(c in "!@#$" for c in pwd):
            return pwd


# ── Execution ─────────────────────────────────────────────────────────────────

def execute_action(db: Session, user: models.User, action_data: dict) -> str:
    """Execute a confirmed action. Returns success message or raises ValueError."""
    action_type = action_data.get("action_type", "")
    params = action_data.get("params", {})

    dispatch = {
        "transfer": _exec_transfer,
        "status_change": _exec_status_change,
        "create_product": _exec_create_product,
        "edit_product": _exec_edit_product,
        "delete_product": _exec_delete_product,
        "create_user": _exec_create_user,
        "deactivate_user": _exec_deactivate_user,
        "reset_password": _exec_reset_password,
    }
    fn = dispatch.get(action_type)
    if not fn:
        raise ValueError(f"Tipo de acción desconocido: {action_type}")

    result_msg, target_id = fn(db, user, params)

    db.add(models.ActionLog(
        user_id=user.id,
        action_type=action_type,
        target_type="user" if action_type in {"create_user", "deactivate_user", "reset_password"} else "stock",
        target_id=target_id,
        action_detail=json.dumps(action_data, ensure_ascii=False),
        confirmed_at=datetime.now(UTC),
        status="success",
    ))
    db.commit()

    _notify_action(db, user, action_type, result_msg)
    db.commit()

    return result_msg


def _record_history(db, user, product_id, product_type, warehouse_id, field, old_val, new_val):
    db.add(models.StockHistory(
        product_id=product_id,
        product_type=product_type,
        warehouse_id=warehouse_id,
        changed_by=user.id,
        field_changed=field,
        old_value=str(old_val),
        new_value=str(new_val),
    ))


def _exec_transfer(db, user, params):
    from_wh = db.query(models.Warehouse).filter_by(code=params["from_warehouse"]).first()
    to_wh = db.query(models.Warehouse).filter_by(code=params["to_warehouse"]).first()
    if not from_wh or not to_wh:
        raise ValueError("Almacén no encontrado.")

    src = db.query(models.Stock).filter_by(
        warehouse_id=from_wh.id, product_code=params["product_code"]
    ).first()
    if not src or src.quantity < params["quantity"]:
        raise ValueError("Stock insuficiente o producto no encontrado.")

    old_qty = src.quantity
    src.quantity -= params["quantity"]
    _record_history(db, user, src.id, "cantidad", from_wh.id, "quantity", old_qty, src.quantity)

    dst = db.query(models.Stock).filter_by(
        warehouse_id=to_wh.id, product_code=params["product_code"]
    ).first()
    if dst:
        old_dst = dst.quantity
        dst.quantity += params["quantity"]
        _record_history(db, user, dst.id, "cantidad", to_wh.id, "quantity", old_dst, dst.quantity)
    else:
        dst = models.Stock(
            warehouse_id=to_wh.id,
            product_code=src.product_code,
            product_name=src.product_name,
            category=src.category,
            quantity=params["quantity"],
            min_quantity=src.min_quantity,
            unit=src.unit,
            location_in_warehouse="",
            status="disponible",
        )
        db.add(dst)
        db.flush()
        _record_history(db, user, dst.id, "cantidad", to_wh.id, "quantity", 0, params["quantity"])

    db.flush()
    inventree_service.sync_transfer(
        src.product_name, params["from_warehouse"], params["to_warehouse"], params["quantity"]
    )
    return (
        f"Transferencia completada: {params['quantity']} unidades de {src.product_name} "
        f"de {from_wh.name} a {to_wh.name}.",
        src.id,
    )


def _exec_status_change(db, user, params):
    identifier = params["product_identifier"]
    wh = db.query(models.Warehouse).filter_by(code=params["warehouse_code"]).first()
    if not wh:
        raise ValueError(f"Almacén '{params['warehouse_code']}' no encontrado.")

    stock = db.query(models.Stock).filter_by(warehouse_id=wh.id, product_code=identifier).first()
    if stock:
        old = stock.status
        stock.status = params["new_status"]
        _record_history(db, user, stock.id, "cantidad", wh.id, "status", old, params["new_status"])
        db.flush()
        inventree_service.sync_status_change(stock.product_name, params["warehouse_code"], params["new_status"])
        return f"Estado de {stock.product_name} cambiado a '{params['new_status']}' en {wh.name}.", stock.id

    serial = db.query(models.StockSerial).filter_by(
        warehouse_id=wh.id, serial_number=identifier
    ).first()
    if serial:
        old = serial.status
        serial.status = params["new_status"]
        _record_history(db, user, serial.id, "serie_unica", wh.id, "status", old, params["new_status"])
        db.flush()
        inventree_service.sync_status_change(serial.product_name, params["warehouse_code"], params["new_status"])
        return f"Estado de {serial.product_name} (SN: {identifier}) cambiado a '{params['new_status']}'.", serial.id

    raise ValueError(f"Producto '{identifier}' no encontrado en {wh.name}.")


def _exec_create_product(db, user, params):
    wh = db.query(models.Warehouse).filter_by(code=params["warehouse_code"]).first()
    if not wh:
        raise ValueError(f"Almacén '{params['warehouse_code']}' no encontrado.")

    product = models.Stock(
        warehouse_id=wh.id,
        product_code=params["product_code"],
        product_name=params["product_name"],
        category=params.get("category", ""),
        quantity=int(params.get("quantity", 0)),
        min_quantity=int(params.get("min_quantity", 0)),
        unit=params.get("unit", "unidad"),
        location_in_warehouse=params.get("location", ""),
        status="disponible",
    )
    db.add(product)
    db.flush()
    _record_history(db, user, product.id, "cantidad", wh.id, "quantity", 0, product.quantity)
    inventree_service.sync_create_product(
        product.product_name, params["warehouse_code"],
        params.get("category", ""), int(params.get("quantity", 0)),
    )
    return f"Producto {product.product_name} ({product.product_code}) creado en {wh.name}.", product.id


def _exec_edit_product(db, user, params):
    wh = db.query(models.Warehouse).filter_by(code=params["warehouse_code"]).first()
    if not wh:
        raise ValueError(f"Almacén '{params['warehouse_code']}' no encontrado.")

    stock = db.query(models.Stock).filter_by(
        warehouse_id=wh.id, product_code=params["product_code"]
    ).first()
    if not stock:
        raise ValueError(f"Producto '{params['product_code']}' no encontrado.")

    field = params["field"]
    old_val = str(getattr(stock, field, ""))
    typed_val = int(params["new_value"]) if field == "min_quantity" else params["new_value"]
    setattr(stock, field, typed_val)
    _record_history(db, user, stock.id, "cantidad", wh.id, field, old_val, params["new_value"])
    db.flush()
    return f"Producto {stock.product_name}: '{field}' actualizado a '{params['new_value']}'.", stock.id


def _exec_delete_product(db, user, params):
    wh = db.query(models.Warehouse).filter_by(code=params["warehouse_code"]).first()
    if not wh:
        raise ValueError(f"Almacén '{params['warehouse_code']}' no encontrado.")

    stock = db.query(models.Stock).filter_by(
        warehouse_id=wh.id, product_code=params["product_code"]
    ).first()
    if not stock:
        raise ValueError(f"Producto '{params['product_code']}' no encontrado.")

    old_status = stock.status
    stock.status = "dado_de_baja"
    _record_history(db, user, stock.id, "cantidad", wh.id, "status", old_status, "dado_de_baja")
    db.flush()
    inventree_service.sync_deactivate_product(stock.product_name)
    return f"Producto {stock.product_name} ({params['product_code']}) dado de baja en {wh.name}.", stock.id


def _exec_create_user(db, user, params):
    role = db.query(models.Role).filter_by(name=params["role_name"]).first()
    if not role:
        raise ValueError(f"Rol '{params['role_name']}' no encontrado.")

    warehouse_id = None
    if params.get("warehouse_code"):
        wh = db.query(models.Warehouse).filter_by(code=params["warehouse_code"]).first()
        if wh:
            warehouse_id = wh.id

    password = params.get("_temp_password") or _gen_temp_password()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    new_user = models.User(
        username=params["username"],
        password_hash=hashed,
        role_id=role.id,
        warehouse_id=warehouse_id,
        full_name=params.get("full_name", ""),
        is_active=True,
    )
    db.add(new_user)
    db.flush()
    inventree_service.sync_create_user(
        params["username"], params.get("full_name", ""),
        params["role_name"], password,
    )
    return f"Usuario {params['username']} ({params['full_name']}) creado con rol {params['role_name']}.", new_user.id


def _exec_deactivate_user(db, user, params):
    target = db.query(models.User).filter_by(username=params["username"]).first()
    if not target:
        raise ValueError(f"Usuario '{params['username']}' no encontrado.")
    target.is_active = False
    db.flush()
    inventree_service.sync_deactivate_user(params["username"])
    return f"Usuario {params['username']} desactivado.", target.id


def _exec_reset_password(db, user, params):
    target = db.query(models.User).filter_by(username=params["username"]).first()
    if not target:
        raise ValueError(f"Usuario '{params['username']}' no encontrado.")
    hashed = bcrypt.hashpw(params["new_password"].encode(), bcrypt.gensalt()).decode()
    target.password_hash = hashed
    db.flush()
    return f"Contraseña de {params['username']} reseteada.", target.id


# ── Notifications ─────────────────────────────────────────────────────────────

def _notify_action(db: Session, user: models.User, action_type: str, detail: str):
    message = f"Acción '{action_type}' por {user.username}: {detail[:200]}"
    notified: set[int] = set()

    if user.role.hierarchy_level > 1:
        admin = (
            db.query(models.User).join(models.Role)
            .filter(models.Role.hierarchy_level == 1, models.User.is_active == True)
            .first()
        )
        if admin:
            db.add(models.Notification(
                recipient_user_id=admin.id,
                type="action_executed",
                message=message,
                related_user_id=user.id,
            ))
            notified.add(admin.id)

    superior = _find_superior(db, user)
    if superior and superior.id not in notified:
        db.add(models.Notification(
            recipient_user_id=superior.id,
            type="action_executed",
            message=message,
            related_user_id=user.id,
        ))
