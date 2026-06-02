"""Metrics service — per-user and global activity metrics."""
from datetime import datetime, UTC, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend import models


def _now_naive() -> datetime:
    """Naive UTC datetime for SQLite filter comparisons."""
    return datetime.now(UTC).replace(tzinfo=None)


def get_user_metrics(db: Session, user_id: int) -> dict:
    now = _now_naive()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    chatbot_today = db.query(models.ChatHistory).filter(
        models.ChatHistory.user_id == user_id,
        models.ChatHistory.timestamp >= today_start,
    ).count()

    chatbot_week = db.query(models.ChatHistory).filter(
        models.ChatHistory.user_id == user_id,
        models.ChatHistory.timestamp >= week_ago,
    ).count()

    stock_mods_month = db.query(models.StockHistory).filter(
        models.StockHistory.changed_by == user_id,
        models.StockHistory.changed_at >= month_ago,
    ).count()

    top_rows = (
        db.query(
            models.StockHistory.product_id,
            func.count(models.StockHistory.id).label("modification_count"),
        )
        .filter(
            models.StockHistory.changed_by == user_id,
            models.StockHistory.product_type == "cantidad",
        )
        .group_by(models.StockHistory.product_id)
        .order_by(func.count(models.StockHistory.id).desc())
        .limit(5)
        .all()
    )

    top_modified_products = []
    for row in top_rows:
        item = db.query(models.Stock).filter_by(id=row.product_id).first()
        if item:
            top_modified_products.append({
                "product_code": item.product_code,
                "product_name": item.product_name,
                "modification_count": row.modification_count,
            })

    last_chat = (
        db.query(models.ChatHistory)
        .filter_by(user_id=user_id)
        .order_by(models.ChatHistory.timestamp.desc())
        .first()
    )
    last_stock = (
        db.query(models.StockHistory)
        .filter_by(changed_by=user_id)
        .order_by(models.StockHistory.changed_at.desc())
        .first()
    )
    last_note = (
        db.query(models.CrmNote)
        .filter_by(user_id=user_id)
        .order_by(models.CrmNote.created_at.desc())
        .first()
    )

    timestamps = [
        t for t in [
            last_chat.timestamp if last_chat else None,
            last_stock.changed_at if last_stock else None,
            last_note.created_at if last_note else None,
        ] if t is not None
    ]
    last_activity = max(timestamps) if timestamps else None

    return {
        "user_id": user_id,
        "chatbot_queries_today": chatbot_today,
        "chatbot_queries_week": chatbot_week,
        "stock_modifications_month": stock_mods_month,
        "top_modified_products": top_modified_products,
        "last_activity": last_activity,
    }


def get_global_metrics(db: Session) -> dict:
    now = _now_naive()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    total_queries_today = db.query(models.ChatHistory).filter(
        models.ChatHistory.timestamp >= today_start,
    ).count()

    total_queries_week = db.query(models.ChatHistory).filter(
        models.ChatHistory.timestamp >= week_ago,
    ).count()

    warehouse_activity = (
        db.query(
            models.StockHistory.warehouse_id,
            func.count(models.StockHistory.id).label("count"),
        )
        .group_by(models.StockHistory.warehouse_id)
        .order_by(func.count(models.StockHistory.id).desc())
        .first()
    )
    most_active_warehouse = None
    if warehouse_activity:
        wh = db.query(models.Warehouse).filter_by(id=warehouse_activity.warehouse_id).first()
        if wh:
            most_active_warehouse = {
                "warehouse_id": wh.id,
                "warehouse_name": wh.name,
                "modification_count": warehouse_activity.count,
            }

    user_chat = dict(
        db.query(models.ChatHistory.user_id, func.count(models.ChatHistory.id))
        .filter(models.ChatHistory.timestamp >= week_ago)
        .group_by(models.ChatHistory.user_id)
        .all()
    )
    user_stock = dict(
        db.query(models.StockHistory.changed_by, func.count(models.StockHistory.id))
        .filter(
            models.StockHistory.changed_at >= week_ago,
            models.StockHistory.changed_by.isnot(None),
        )
        .group_by(models.StockHistory.changed_by)
        .all()
    )
    combined: dict[int, int] = {}
    for uid, cnt in user_chat.items():
        combined[uid] = combined.get(uid, 0) + cnt
    for uid, cnt in user_stock.items():
        combined[uid] = combined.get(uid, 0) + cnt

    top_users = []
    for uid, cnt in sorted(combined.items(), key=lambda x: x[1], reverse=True)[:5]:
        u = db.query(models.User).filter_by(id=uid).first()
        if u:
            top_users.append({
                "user_id": uid,
                "username": u.username,
                "activity_count": cnt,
            })

    return {
        "total_queries_today": total_queries_today,
        "total_queries_week": total_queries_week,
        "most_active_warehouse": most_active_warehouse,
        "top_users": top_users,
    }
