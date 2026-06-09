"""Admin-only write tools for user management."""
from langchain_core.tools import tool

VALID_ROLES = {"admin", "gestor", "supervisor", "operador"}


def make_admin_write_tools(action_holder: dict) -> list:
    """User management tools — admin only."""

    @tool("propose_create_user")
    def propose_create_user(
        username: str,
        full_name: str,
        role_name: str,
        warehouse_code: str = "",
    ) -> str:
        """Propone crear un nuevo usuario en el sistema.
        NO crea el usuario — el admin debe confirmar.

        Args:
            username: Nombre de usuario único (sin espacios)
            full_name: Nombre completo
            role_name: Rol: admin | gestor | supervisor | operador
            warehouse_code: Código del almacén asignado (obligatorio para supervisor y operador)
        """
        if role_name not in VALID_ROLES:
            return f"Rol inválido: '{role_name}'. Válidos: {', '.join(VALID_ROLES)}"
        action_holder["action"] = {
            "action_type": "create_user",
            "params": {
                "username": username.lower().replace(" ", "_"),
                "full_name": full_name,
                "role_name": role_name,
                "warehouse_code": warehouse_code.upper() if warehouse_code else "",
            },
        }
        return "ACCION_PROPUESTA"

    @tool("propose_deactivate_user")
    def propose_deactivate_user(username: str) -> str:
        """Propone desactivar un usuario (no podrá iniciar sesión).
        Sus datos se conservan. NO desactiva — el admin debe confirmar.

        Args:
            username: Nombre de usuario a desactivar
        """
        action_holder["action"] = {
            "action_type": "deactivate_user",
            "params": {"username": username},
        }
        return "ACCION_PROPUESTA"

    @tool("propose_reset_password")
    def propose_reset_password(username: str, new_password: str) -> str:
        """Propone resetear la contraseña de un usuario.
        La contraseña debe tener mínimo 8 caracteres, 1 mayúscula, 1 número y 1 carácter especial.
        NO cambia la contraseña — el admin debe confirmar.

        Args:
            username: Nombre de usuario
            new_password: Nueva contraseña temporal
        """
        action_holder["action"] = {
            "action_type": "reset_password",
            "params": {
                "username": username,
                "new_password": new_password,
            },
        }
        return "ACCION_PROPUESTA"

    return [propose_create_user, propose_deactivate_user, propose_reset_password]
