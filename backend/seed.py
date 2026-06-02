"""Populate DB with initial roles, warehouses, users, and stock for testing."""
from datetime import datetime, UTC
import bcrypt
from backend.database import SessionLocal, engine, Base
from backend import models


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(models.Role).count() > 0:
        print("DB already seeded. Skipping.")
        db.close()
        return

    # Roles
    roles = [
        models.Role(
            id=1, name="admin", hierarchy_level=1,
            system_prompt=(
                "Eres un asistente de gestión de inventario. "
                "Tienes acceso completo a todos los almacenes. "
                "Responde con toda la información disponible sin restricciones."
            ),
        ),
        models.Role(
            id=2, name="gestor", hierarchy_level=2,
            system_prompt=(
                "Eres un asistente de gestión de inventario. "
                "Tienes acceso al stock de todos los almacenes. "
                "Cuando un producto no esté disponible en un almacén, "
                "puedes indicar si está en otro."
            ),
        ),
        models.Role(
            id=3, name="supervisor", hierarchy_level=3,
            system_prompt=(
                "Eres un asistente de inventario de {warehouse_name}. "
                "Solo tienes información de este almacén. "
                "Si un producto no está disponible aquí, indica que no está "
                "disponible en este almacén. No menciones otros almacenes."
            ),
        ),
        models.Role(
            id=4, name="operador", hierarchy_level=4,
            system_prompt=(
                "Eres un asistente de inventario de {warehouse_name}. "
                "Solo tienes información de este almacén. "
                "Si un producto no está disponible aquí, indica que no está "
                "disponible en este almacén. No menciones otros almacenes."
            ),
        ),
    ]
    db.add_all(roles)
    db.flush()

    # Warehouses
    wh_a = models.Warehouse(
        code="ALM-A", name="Almacén Norte",
        agent_url="http://localhost:8001/stock",
        agent_token="token-alm-a",
        is_online=True, last_seen=datetime.now(UTC),
    )
    wh_b = models.Warehouse(
        code="ALM-B", name="Almacén Sur",
        agent_url="http://localhost:8002/stock",
        agent_token="token-alm-b",
        is_online=True, last_seen=datetime.now(UTC),
    )
    db.add_all([wh_a, wh_b])
    db.flush()

    # Users
    users = [
        models.User(username="admin", password_hash=hash_password("Admin123!"),
                    role_id=1, warehouse_id=None, full_name="Administrador"),
        models.User(username="gestor1", password_hash=hash_password("Gestor123!"),
                    role_id=2, warehouse_id=None, full_name="Gestor General"),
        models.User(username="supervisor_a", password_hash=hash_password("Super123!"),
                    role_id=3, warehouse_id=wh_a.id, full_name="Supervisor Norte"),
        models.User(username="supervisor_b", password_hash=hash_password("Super123!"),
                    role_id=3, warehouse_id=wh_b.id, full_name="Supervisor Sur"),
        models.User(username="operador_a1", password_hash=hash_password("Oper123!"),
                    role_id=4, warehouse_id=wh_a.id, full_name="Operador Norte 1"),
        models.User(username="operador_b1", password_hash=hash_password("Oper123!"),
                    role_id=4, warehouse_id=wh_b.id, full_name="Operador Sur 1"),
    ]
    db.add_all(users)
    db.flush()

    # Stock Almacén Norte (cantidad)
    stock_a = [
        models.Stock(warehouse_id=wh_a.id, product_code="P001",
                     product_name="Filtro de aceite", category="Filtros",
                     quantity=45, min_quantity=10, unit="unidad",
                     location_in_warehouse="Estante B-3", status="disponible"),
        models.Stock(warehouse_id=wh_a.id, product_code="P002",
                     product_name="Correa de distribución", category="Motor",
                     quantity=8, min_quantity=5, unit="unidad",
                     location_in_warehouse="Estante A-1", status="disponible"),
        models.Stock(warehouse_id=wh_a.id, product_code="P003",
                     product_name="Bujías NGK", category="Encendido",
                     quantity=3, min_quantity=10, unit="juego",
                     location_in_warehouse="Estante C-2", status="disponible"),
        models.Stock(warehouse_id=wh_a.id, product_code="P004",
                     product_name="Aceite motor 5W30", category="Lubricantes",
                     quantity=22, min_quantity=5, unit="litro",
                     location_in_warehouse="Zona D", status="disponible"),
    ]

    # Stock Almacén Sur (cantidad)
    stock_b = [
        models.Stock(warehouse_id=wh_b.id, product_code="P001",
                     product_name="Filtro de aceite", category="Filtros",
                     quantity=12, min_quantity=10, unit="unidad",
                     location_in_warehouse="Rack 1-A", status="disponible"),
        models.Stock(warehouse_id=wh_b.id, product_code="P005",
                     product_name="Pastillas de freno", category="Frenos",
                     quantity=0, min_quantity=8, unit="juego",
                     location_in_warehouse="Rack 2-B", status="dado_de_baja"),
        models.Stock(warehouse_id=wh_b.id, product_code="P006",
                     product_name="Amortiguador delantero", category="Suspensión",
                     quantity=6, min_quantity=2, unit="unidad",
                     location_in_warehouse="Zona E", status="disponible"),
    ]

    db.add_all(stock_a + stock_b)

    # Stock serie única — Almacén Norte
    serials_a = [
        models.StockSerial(warehouse_id=wh_a.id, product_code="ME-5HP",
                           serial_number="SN-2041",
                           product_name="Motor eléctrico 5HP", category="Motores",
                           location_in_warehouse="Zona C", status="disponible"),
        models.StockSerial(warehouse_id=wh_a.id, product_code="ME-5HP",
                           serial_number="SN-2042",
                           product_name="Motor eléctrico 5HP", category="Motores",
                           location_in_warehouse="Zona C", status="en_reparacion"),
    ]

    # Stock serie única — Almacén Sur
    serials_b = [
        models.StockSerial(warehouse_id=wh_b.id, product_code="COMP-2T",
                           serial_number="SN-3001",
                           product_name="Compresor 2 toneladas", category="Compresores",
                           location_in_warehouse="Zona F", status="disponible"),
        models.StockSerial(warehouse_id=wh_b.id, product_code="COMP-2T",
                           serial_number="SN-3002",
                           product_name="Compresor 2 toneladas", category="Compresores",
                           location_in_warehouse="Zona F", status="reservado"),
    ]

    db.add_all(serials_a + serials_b)
    db.commit()
    db.close()
    print("Seed OK — roles, warehouses, users, stock loaded.")


if __name__ == "__main__":
    seed()
