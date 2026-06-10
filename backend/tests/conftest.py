"""Shared pytest fixtures: in-memory DB with seed data."""
import bcrypt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database import Base
from backend import models
from backend.main import app
from backend.database import get_db
from backend.services.auth_service import create_access_token


# ── In-memory SQLite DB ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # all connections share the same in-memory DB
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _make_user_token(db, user: models.User) -> str:
    """Create a JWT + Session row for the user and return the token string."""
    token_str, jti = create_access_token(user.id, user.role.name)
    from datetime import datetime, UTC, timedelta
    sess = models.Session(
        user_id=user.id,
        jti=jti,
        is_revoked=False,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(sess)
    db.commit()
    return token_str


@pytest.fixture
def seeded_db(db):
    """DB with two warehouses, roles, and one user per role + stock items."""
    pw = bcrypt.hashpw(b"test1234", bcrypt.gensalt()).decode()

    roles = [
        models.Role(id=10, name="admin", hierarchy_level=1, system_prompt=""),
        models.Role(id=11, name="gestor", hierarchy_level=2, system_prompt=""),
        models.Role(id=12, name="supervisor", hierarchy_level=3, system_prompt=""),
        models.Role(id=13, name="operador", hierarchy_level=4, system_prompt=""),
    ]
    for r in roles:
        db.merge(r)

    wh_a = models.Warehouse(id=10, code="ALM-A", name="Almacén Norte", agent_url="", agent_token="")
    wh_b = models.Warehouse(id=11, code="ALM-B", name="Almacén Sur", agent_url="", agent_token="")
    db.merge(wh_a)
    db.merge(wh_b)

    users = [
        models.User(id=10, username="admin_u", password_hash=pw, role_id=10, warehouse_id=None),
        models.User(id=11, username="gestor_u", password_hash=pw, role_id=11, warehouse_id=None),
        models.User(id=12, username="supervisor_u", password_hash=pw, role_id=12, warehouse_id=10),
        models.User(id=13, username="operador_u", password_hash=pw, role_id=13, warehouse_id=10),
    ]
    for u in users:
        db.merge(u)

    stock = [
        models.Stock(id=10, warehouse_id=10, product_code="P001", product_name="Laptop Dell",
                     category="Electrónica", quantity=10, min_quantity=2, status="disponible"),
        models.Stock(id=11, warehouse_id=10, product_code="P002", product_name="Mouse Logitech",
                     category="Periféricos", quantity=3, min_quantity=5, status="disponible"),
        models.Stock(id=12, warehouse_id=11, product_code="P001", product_name="Laptop Dell",
                     category="Electrónica", quantity=5, min_quantity=2, status="disponible"),
        models.Stock(id=13, warehouse_id=10, product_code="P003", product_name="Teclado HP",
                     category="Periféricos", quantity=0, min_quantity=1, status="dado_de_baja"),
    ]
    for s in stock:
        db.merge(s)

    db.commit()
    return db


@pytest.fixture
def client(seeded_db):
    def override_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers(seeded_db):
    user = seeded_db.query(models.User).filter_by(username="admin_u").first()
    token = _make_user_token(seeded_db, user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operador_headers(seeded_db):
    user = seeded_db.query(models.User).filter_by(username="operador_u").first()
    token = _make_user_token(seeded_db, user)
    return {"Authorization": f"Bearer {token}"}
