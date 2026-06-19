"""Sync confirmed chatbot actions to InvenTree (Spiga+ simulator).

All functions are fire-and-forget: errors are logged but never propagate
so a downed InvenTree never blocks a confirmed action.
"""
import logging

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

# Map backend status names → InvenTree status codes
STATUS_MAP = {
    "disponible": 10,
    "en_reparacion": 50,
    "reservado": 60,
    "dado_de_baja": 75,
}

# Map warehouse codes → InvenTree location name keywords
WAREHOUSE_KEYWORD = {
    "ALM-A": "Norte",
    "ALM-B": "Sur",
}


def _headers() -> dict:
    return {
        "Authorization": f"Token {settings.inventree_token}",
        "Content-Type": "application/json",
    }


def _get(endpoint: str, params: dict | None = None):
    r = httpx.get(
        f"{settings.inventree_url}{endpoint}",
        headers=_headers(),
        params=params,
        timeout=8,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("results", data) if isinstance(data, dict) and "results" in data else data


def _patch(endpoint: str, data: dict):
    r = httpx.patch(
        f"{settings.inventree_url}{endpoint}",
        headers=_headers(),
        json=data,
        timeout=8,
    )
    r.raise_for_status()
    return r.json()


def _post(endpoint: str, data: dict):
    r = httpx.post(
        f"{settings.inventree_url}{endpoint}",
        headers=_headers(),
        json=data,
        timeout=8,
    )
    r.raise_for_status()
    return r.json()


def _find_part_pk(product_name: str) -> int | None:
    parts = _get("part/", {"search": product_name, "limit": 10})
    for part in parts:
        if part["name"].lower() == product_name.lower():
            return part["pk"]
    return parts[0]["pk"] if parts else None


def _find_location_pk(warehouse_code: str) -> int | None:
    names = {"ALM-A": "Almacén Norte", "ALM-B": "Almacén Sur"}
    name = names.get(warehouse_code)
    if not name:
        return None
    locations = _get("stock/location/", {"name": name, "limit": 5})
    return locations[0]["pk"] if locations else None


def _stock_items_for_part(part_pk: int, warehouse_code: str | None = None) -> list:
    items = _get("stock/", {"part": part_pk, "limit": 100, "location_detail": True})
    if not warehouse_code:
        return items
    keyword = WAREHOUSE_KEYWORD.get(warehouse_code, "").lower()
    return [
        item for item in items
        if keyword in ((item.get("location_detail") or {}).get("pathstring", "")).lower()
    ]


# ── Public sync functions ─────────────────────────────────────────────────────

def sync_transfer(product_name: str, from_wh: str, to_wh: str, quantity: int) -> None:
    if not settings.inventree_token:
        return
    try:
        part_pk = _find_part_pk(product_name)
        if not part_pk:
            logger.warning("[InvenTree] part not found: %s", product_name)
            return

        items = _stock_items_for_part(part_pk, from_wh)
        if not items:
            logger.warning("[InvenTree] no stock in %s for %s", from_wh, product_name)
            return

        to_location = _find_location_pk(to_wh)
        if not to_location:
            logger.warning("[InvenTree] location not found for %s", to_wh)
            return

        source = items[0]
        transfer_qty = min(quantity, int(source.get("quantity", 0)))
        _post("stock/transfer/", {
            "items": [{"pk": source["pk"], "quantity": transfer_qty}],
            "location": to_location,
            "notes": "Transferencia vía chatbot MVP",
        })
        logger.info("[InvenTree] transfer OK: %dx %s %s→%s", transfer_qty, product_name, from_wh, to_wh)
    except Exception as exc:
        logger.warning("[InvenTree] sync_transfer error: %s", exc)


def sync_status_change(product_name: str, warehouse_code: str, new_status: str) -> None:
    if not settings.inventree_token:
        return
    try:
        part_pk = _find_part_pk(product_name)
        if not part_pk:
            return
        inv_status = STATUS_MAP.get(new_status, 10)
        items = _stock_items_for_part(part_pk, warehouse_code)
        for item in items:
            _patch(f"stock/{item['pk']}/", {"status": inv_status})
        logger.info("[InvenTree] status→%s for %s in %s", new_status, product_name, warehouse_code)
    except Exception as exc:
        logger.warning("[InvenTree] sync_status_change error: %s", exc)


def sync_create_product(
    product_name: str,
    warehouse_code: str,
    category: str,
    quantity: int,
) -> None:
    if not settings.inventree_token:
        return
    try:
        cats = _get("part/category/", {"search": category, "limit": 5})
        cat_pk = cats[0]["pk"] if cats else None

        part = _post("part/", {
            "name": product_name,
            "category": cat_pk,
            "active": True,
            "trackable": False,
        })

        loc_pk = _find_location_pk(warehouse_code)
        _post("stock/", {"part": part["pk"], "quantity": quantity, "location": loc_pk})
        logger.info("[InvenTree] created part '%s' (%d units)", product_name, quantity)
    except Exception as exc:
        logger.warning("[InvenTree] sync_create_product error: %s", exc)


def sync_create_user(username: str, full_name: str, role_name: str, password: str) -> None:
    if not settings.inventree_token:
        return
    try:
        is_staff = role_name in ("admin", "gestor", "supervisor")
        is_superuser = role_name == "admin"
        first, *rest = (full_name or username).split(" ", 1)
        last = rest[0] if rest else ""
        _post("user/", {
            "username": username,
            "email": f"{username}@demo.com",
            "password": password,
            "first_name": first,
            "last_name": last,
            "is_staff": is_staff,
            "is_superuser": is_superuser,
        })
        logger.info("[InvenTree] user created: %s (%s)", username, role_name)
    except Exception as exc:
        logger.warning("[InvenTree] sync_create_user error: %s", exc)


def sync_deactivate_user(username: str) -> None:
    if not settings.inventree_token:
        return
    try:
        users = _get("user/", {"limit": 100})
        for u in users:
            if u.get("username") == username:
                _patch(f"user/{u['pk']}/", {"is_active": False})
                logger.info("[InvenTree] user deactivated: %s", username)
                return
    except Exception as exc:
        logger.warning("[InvenTree] sync_deactivate_user error: %s", exc)


def sync_deactivate_product(product_name: str) -> None:
    if not settings.inventree_token:
        return
    try:
        part_pk = _find_part_pk(product_name)
        if part_pk:
            _patch(f"part/{part_pk}/", {"active": False})
            logger.info("[InvenTree] deactivated part '%s'", product_name)
    except Exception as exc:
        logger.warning("[InvenTree] sync_deactivate_product error: %s", exc)
