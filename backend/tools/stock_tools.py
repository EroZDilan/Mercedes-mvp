"""Write tools that PROPOSE stock actions — never execute directly."""
from langchain_core.tools import tool

VALID_STATUSES = {"disponible", "reservado", "en_reparacion", "dado_de_baja"}
EDITABLE_FIELDS = {"product_name", "category", "min_quantity", "unit", "location_in_warehouse"}


def make_stock_write_tools(action_holder: dict) -> list:
    """Transfer + status change — available to all roles."""

    @tool("propose_transfer")
    def propose_transfer(
        product_code: str,
        quantity: int,
        from_warehouse_code: str,
        to_warehouse_code: str,
    ) -> str:
        """Propone transferir una cantidad de un producto entre almacenes.
        NO ejecuta nada — el usuario debe confirmar antes de que se aplique.

        Args:
            product_code: Código del producto (ej: P001)
            quantity: Cantidad a transferir (entero positivo)
            from_warehouse_code: Código del almacén origen (ej: ALM-A)
            to_warehouse_code: Código del almacén destino (ej: ALM-B)
        """
        if int(quantity) <= 0:
            return "La cantidad debe ser mayor que cero."
        action_holder["action"] = {
            "action_type": "transfer",
            "params": {
                "product_code": product_code.upper(),
                "quantity": int(quantity),
                "from_warehouse": from_warehouse_code.upper(),
                "to_warehouse": to_warehouse_code.upper(),
            },
        }
        return "ACCION_PROPUESTA"

    @tool("propose_status_change")
    def propose_status_change(
        product_identifier: str,
        warehouse_code: str,
        new_status: str,
    ) -> str:
        """Propone cambiar el estado de un producto (por cantidad o serie única).
        NO ejecuta nada — el usuario debe confirmar.

        Args:
            product_identifier: Código del producto (P001) o número de serie (SN-2041)
            warehouse_code: Código del almacén (ALM-A, ALM-B)
            new_status: disponible | reservado | en_reparacion | dado_de_baja
        """
        if new_status not in VALID_STATUSES:
            return f"Estado inválido: '{new_status}'. Valores: {', '.join(VALID_STATUSES)}"
        action_holder["action"] = {
            "action_type": "status_change",
            "params": {
                "product_identifier": product_identifier,
                "warehouse_code": warehouse_code.upper(),
                "new_status": new_status,
            },
        }
        return "ACCION_PROPUESTA"

    return [propose_transfer, propose_status_change]


def make_supervisor_write_tools(action_holder: dict) -> list:
    """Create + edit products — available to supervisor and above."""

    @tool("propose_create_product")
    def propose_create_product(
        warehouse_code: str,
        product_code: str,
        product_name: str,
        category: str,
        quantity: int,
        min_quantity: int,
        unit: str = "unidad",
        location: str = "",
    ) -> str:
        """Propone crear un nuevo producto en un almacén.
        NO ejecuta nada — el usuario debe confirmar.

        Args:
            warehouse_code: Código del almacén (ALM-A, ALM-B)
            product_code: Código único del producto (ej: P007)
            product_name: Nombre descriptivo del producto
            category: Categoría del producto
            quantity: Cantidad inicial en stock
            min_quantity: Stock mínimo para alertas
            unit: Unidad de medida (unidad, litro, kg, etc.)
            location: Ubicación física en el almacén (opcional)
        """
        action_holder["action"] = {
            "action_type": "create_product",
            "params": {
                "warehouse_code": warehouse_code.upper(),
                "product_code": product_code.upper(),
                "product_name": product_name,
                "category": category,
                "quantity": int(quantity),
                "min_quantity": int(min_quantity),
                "unit": unit,
                "location": location,
            },
        }
        return "ACCION_PROPUESTA"

    @tool("propose_edit_product")
    def propose_edit_product(
        warehouse_code: str,
        product_code: str,
        field: str,
        new_value: str,
    ) -> str:
        """Propone editar un campo de un producto existente.
        NO ejecuta nada — el usuario debe confirmar.

        Args:
            warehouse_code: Código del almacén (ALM-A, ALM-B)
            product_code: Código del producto (ej: P001)
            field: Campo a modificar: product_name, category, min_quantity, unit, location_in_warehouse
            new_value: Nuevo valor para el campo
        """
        if field not in EDITABLE_FIELDS:
            return f"Campo '{field}' no editable. Permitidos: {', '.join(EDITABLE_FIELDS)}"
        action_holder["action"] = {
            "action_type": "edit_product",
            "params": {
                "warehouse_code": warehouse_code.upper(),
                "product_code": product_code.upper(),
                "field": field,
                "new_value": new_value,
            },
        }
        return "ACCION_PROPUESTA"

    return [propose_create_product, propose_edit_product]


def make_gestor_write_tools(action_holder: dict) -> list:
    """Delete products — available to gestor and above."""

    @tool("propose_delete_product")
    def propose_delete_product(warehouse_code: str, product_code: str) -> str:
        """Propone dar de baja un producto del sistema en un almacén.
        NO ejecuta nada — el usuario debe confirmar.

        Args:
            warehouse_code: Código del almacén (ALM-A, ALM-B)
            product_code: Código del producto a dar de baja (ej: P001)
        """
        action_holder["action"] = {
            "action_type": "delete_product",
            "params": {
                "warehouse_code": warehouse_code.upper(),
                "product_code": product_code.upper(),
            },
        }
        return "ACCION_PROPUESTA"

    return [propose_delete_product]
