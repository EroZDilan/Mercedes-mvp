"""Tests for stock write tools (propose_* functions)."""
import pytest
from backend.tools.stock_tools import (
    make_stock_write_tools,
    make_supervisor_write_tools,
    make_gestor_write_tools,
)


class TestProposeTransfer:
    def test_valid_transfer_sets_action(self):
        holder = {}
        [propose_transfer, _] = make_stock_write_tools(holder)
        result = propose_transfer.invoke({
            "product_code": "p001",
            "quantity": 5,
            "from_warehouse_code": "alm-a",
            "to_warehouse_code": "alm-b",
        })
        assert result == "ACCION_PROPUESTA"
        assert holder["action"]["action_type"] == "transfer"
        params = holder["action"]["params"]
        assert params["product_code"] == "P001"
        assert params["quantity"] == 5
        assert params["from_warehouse"] == "ALM-A"
        assert params["to_warehouse"] == "ALM-B"

    def test_zero_quantity_returns_error(self):
        holder = {}
        [propose_transfer, _] = make_stock_write_tools(holder)
        result = propose_transfer.invoke({
            "product_code": "P001", "quantity": 0,
            "from_warehouse_code": "ALM-A", "to_warehouse_code": "ALM-B",
        })
        assert "mayor que cero" in result
        assert "action" not in holder

    def test_negative_quantity_returns_error(self):
        holder = {}
        [propose_transfer, _] = make_stock_write_tools(holder)
        result = propose_transfer.invoke({
            "product_code": "P001", "quantity": -3,
            "from_warehouse_code": "ALM-A", "to_warehouse_code": "ALM-B",
        })
        assert "mayor que cero" in result


class TestProposeStatusChange:
    def test_valid_status_change(self):
        holder = {}
        [_, propose_status] = make_stock_write_tools(holder)
        result = propose_status.invoke({
            "product_identifier": "P001",
            "warehouse_code": "alm-a",
            "new_status": "reservado",
        })
        assert result == "ACCION_PROPUESTA"
        assert holder["action"]["action_type"] == "status_change"
        assert holder["action"]["params"]["new_status"] == "reservado"
        assert holder["action"]["params"]["warehouse_code"] == "ALM-A"

    def test_invalid_status_returns_error(self):
        holder = {}
        [_, propose_status] = make_stock_write_tools(holder)
        result = propose_status.invoke({
            "product_identifier": "P001",
            "warehouse_code": "ALM-A",
            "new_status": "inexistente",
        })
        assert "Estado inválido" in result
        assert "action" not in holder

    @pytest.mark.parametrize("status", ["disponible", "reservado", "en_reparacion", "dado_de_baja"])
    def test_all_valid_statuses_accepted(self, status):
        holder = {}
        [_, propose_status] = make_stock_write_tools(holder)
        result = propose_status.invoke({
            "product_identifier": "P001", "warehouse_code": "ALM-A", "new_status": status,
        })
        assert result == "ACCION_PROPUESTA"


class TestProposeCreateProduct:
    def test_creates_action(self):
        holder = {}
        [propose_create, _] = make_supervisor_write_tools(holder)
        result = propose_create.invoke({
            "warehouse_code": "alm-a", "product_code": "p099",
            "product_name": "Tablet", "category": "Electrónica",
            "quantity": 10, "min_quantity": 2,
        })
        assert result == "ACCION_PROPUESTA"
        assert holder["action"]["action_type"] == "create_product"
        assert holder["action"]["params"]["product_code"] == "P099"
        assert holder["action"]["params"]["warehouse_code"] == "ALM-A"


class TestProposeEditProduct:
    def test_valid_field_edit(self):
        holder = {}
        [_, propose_edit] = make_supervisor_write_tools(holder)
        result = propose_edit.invoke({
            "warehouse_code": "ALM-A", "product_code": "P001",
            "field": "product_name", "new_value": "Laptop HP",
        })
        assert result == "ACCION_PROPUESTA"
        assert holder["action"]["params"]["field"] == "product_name"

    def test_invalid_field_returns_error(self):
        holder = {}
        [_, propose_edit] = make_supervisor_write_tools(holder)
        result = propose_edit.invoke({
            "warehouse_code": "ALM-A", "product_code": "P001",
            "field": "password", "new_value": "hack",
        })
        assert "no editable" in result


class TestProposeDeleteProduct:
    def test_delete_sets_action(self):
        holder = {}
        [propose_delete] = make_gestor_write_tools(holder)
        result = propose_delete.invoke({"warehouse_code": "alm-b", "product_code": "p001"})
        assert result == "ACCION_PROPUESTA"
        assert holder["action"]["action_type"] == "delete_product"
        assert holder["action"]["params"]["warehouse_code"] == "ALM-B"
