"""Maps user roles to their allowed LangChain tools."""
from sqlalchemy.orm import Session
from backend import models
from backend.tools.query_tools import make_query_tools
from backend.tools.stock_tools import (
    make_stock_write_tools,
    make_supervisor_write_tools,
    make_gestor_write_tools,
)
from backend.tools.admin_tools import make_admin_write_tools


def get_tools_for_user(db: Session, user: models.User, action_holder: dict) -> list:
    """Return all LangChain tools available to this user based on hierarchy_level."""
    level = user.role.hierarchy_level
    tools = []

    # Read tools: all roles
    tools += make_query_tools(db, user)

    # Write tools: all roles can propose transfers and status changes
    tools += make_stock_write_tools(action_holder)

    # Supervisor (3) and above: can create and edit products
    if level <= 3:
        tools += make_supervisor_write_tools(action_holder)

    # Gestor (2) and above: can delete products
    if level <= 2:
        tools += make_gestor_write_tools(action_holder)

    # Admin (1) only: user management
    if level == 1:
        tools += make_admin_write_tools(action_holder)

    return tools
