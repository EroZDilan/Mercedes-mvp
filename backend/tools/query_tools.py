"""Read-only query tools — used by all roles to fetch live stock data."""
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from backend import models


def make_query_tools(db: Session, user: models.User) -> list:
    """Return query tools scoped to the user's warehouse access."""
    accessible_ids = _accessible_wh_ids(db, user)

    @tool("query_stock")
    def query_stock(warehouse_code: str = "", product_search: str = "") -> str:
        """Consulta productos de inventario por cantidad.

        Args:
            warehouse_code: Código del almacén (ALM-A, ALM-B). Vacío = todos los accesibles.
            product_search: Nombre o código parcial del producto. Vacío = todos.

        Devuelve lista con cantidad, estado y ubicación de cada producto.
        """
        q = db.query(models.Stock).filter(models.Stock.warehouse_id.in_(accessible_ids))

        if warehouse_code:
            wh = db.query(models.Warehouse).filter_by(code=warehouse_code.upper()).first()
            if not wh:
                return f"Almacén '{warehouse_code}' no encontrado."
            if wh.id not in accessible_ids:
                return "No tienes acceso a ese almacén."
            q = q.filter(models.Stock.warehouse_id == wh.id)

        if product_search:
            pat = f"%{product_search}%"
            q = q.filter(
                models.Stock.product_name.ilike(pat) | models.Stock.product_code.ilike(pat)
            )

        items = q.filter(models.Stock.status != "dado_de_baja").all()
        if not items:
            return "No se encontraron productos con esos criterios."

        wh_cache: dict[int, str] = {}
        lines = []
        for s in items:
            if s.warehouse_id not in wh_cache:
                wh = db.query(models.Warehouse).filter_by(id=s.warehouse_id).first()
                wh_cache[s.warehouse_id] = wh.name if wh else str(s.warehouse_id)
            lines.append(
                f"[{wh_cache[s.warehouse_id]}] {s.product_code} | {s.product_name} | "
                f"cant: {s.quantity} | mín: {s.min_quantity} | "
                f"estado: {s.status} | ubic: {s.location_in_warehouse or 'N/A'}"
            )
        return "\n".join(lines)

    @tool("query_serial_stock")
    def query_serial_stock(
        warehouse_code: str = "",
        product_search: str = "",
        status_filter: str = "",
    ) -> str:
        """Consulta productos de serie única (con número de serie individual).

        Args:
            warehouse_code: Código del almacén (ALM-A, ALM-B). Vacío = todos los accesibles.
            product_search: Nombre, código o número de serie parcial. Vacío = todos.
            status_filter: disponible | reservado | en_reparacion. Vacío = todos excepto dado_de_baja.
        """
        q = db.query(models.StockSerial).filter(
            models.StockSerial.warehouse_id.in_(accessible_ids)
        )

        if warehouse_code:
            wh = db.query(models.Warehouse).filter_by(code=warehouse_code.upper()).first()
            if not wh:
                return f"Almacén '{warehouse_code}' no encontrado."
            if wh.id not in accessible_ids:
                return "No tienes acceso a ese almacén."
            q = q.filter(models.StockSerial.warehouse_id == wh.id)

        if product_search:
            pat = f"%{product_search}%"
            q = q.filter(
                models.StockSerial.product_name.ilike(pat)
                | models.StockSerial.product_code.ilike(pat)
                | models.StockSerial.serial_number.ilike(pat)
            )

        if status_filter:
            q = q.filter(models.StockSerial.status == status_filter)
        else:
            q = q.filter(models.StockSerial.status != "dado_de_baja")

        items = q.all()
        if not items:
            return "No se encontraron productos de serie única con esos criterios."

        wh_cache: dict[int, str] = {}
        lines = []
        for s in items:
            if s.warehouse_id not in wh_cache:
                wh = db.query(models.Warehouse).filter_by(id=s.warehouse_id).first()
                wh_cache[s.warehouse_id] = wh.name if wh else str(s.warehouse_id)
            lines.append(
                f"[{wh_cache[s.warehouse_id]}] SN: {s.serial_number} | "
                f"{s.product_name} ({s.product_code}) | "
                f"estado: {s.status} | ubic: {s.location_in_warehouse or 'N/A'}"
            )
        return "\n".join(lines)

    return [query_stock, query_serial_stock]


def _accessible_wh_ids(db: Session, user: models.User) -> list[int]:
    if user.role.hierarchy_level <= 2:
        return [w.id for w in db.query(models.Warehouse).all()]
    return [user.warehouse_id] if user.warehouse_id else []
