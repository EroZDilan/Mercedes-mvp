"""Tests for query_tools — no LLM, just the DB-query functions."""
import pytest
from backend.tools.query_tools import make_query_tools
from backend import models


def _get_user(db, username):
    return db.query(models.User).filter_by(username=username).options(
        __import__("sqlalchemy.orm", fromlist=["joinedload"]).joinedload(models.User.role),
        __import__("sqlalchemy.orm", fromlist=["joinedload"]).joinedload(models.User.warehouse),
    ).first()


class TestQueryStock:
    def test_returns_available_items(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        [query_stock, _] = make_query_tools(seeded_db, user)
        result = query_stock.invoke({"warehouse_code": "ALM-A", "product_search": ""})
        assert "P001" in result
        assert "Laptop Dell" in result

    def test_excludes_dado_de_baja(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        [query_stock, _] = make_query_tools(seeded_db, user)
        result = query_stock.invoke({"warehouse_code": "ALM-A", "product_search": ""})
        # P003 is dado_de_baja — must not appear
        assert "P003" not in result

    def test_product_search_filter(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        [query_stock, _] = make_query_tools(seeded_db, user)
        result = query_stock.invoke({"warehouse_code": "", "product_search": "Mouse"})
        assert "Mouse" in result
        assert "Laptop" not in result

    def test_unknown_warehouse_returns_error(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        [query_stock, _] = make_query_tools(seeded_db, user)
        result = query_stock.invoke({"warehouse_code": "NOPE", "product_search": ""})
        assert "no encontrado" in result.lower()

    def test_operador_sees_only_own_warehouse(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="operador_u").first()
        [query_stock, _] = make_query_tools(seeded_db, user)
        # ALM-B should be off-limits for operador (warehouse_id=10 = ALM-A)
        result = query_stock.invoke({"warehouse_code": "ALM-B", "product_search": ""})
        assert "No tienes acceso" in result

    def test_admin_sees_all_warehouses(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        [query_stock, _] = make_query_tools(seeded_db, user)
        result = query_stock.invoke({"warehouse_code": "", "product_search": ""})
        assert "ALM-A" in result or "Almacén Norte" in result
        assert "ALM-B" in result or "Almacén Sur" in result

    def test_empty_db_returns_no_products_message(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        [query_stock, _] = make_query_tools(seeded_db, user)
        result = query_stock.invoke({"warehouse_code": "", "product_search": "XYZ_INEXISTENTE"})
        assert "no se encontraron" in result.lower()


class TestQuerySerialStock:
    def test_returns_not_found_when_no_serials(self, seeded_db):
        user = seeded_db.query(models.User).filter_by(username="admin_u").first()
        [_, query_serial] = make_query_tools(seeded_db, user)
        result = query_serial.invoke({"warehouse_code": "", "product_search": "", "status_filter": ""})
        assert "no se encontraron" in result.lower()
