from fastapi.encoders import jsonable_encoder

from app.models import AuditLog


def add_audit(db, *, actor_id, action: str, entity_type: str, entity_id=None, brand_id=None, details=None, ip_address=None):
    """Append an audit entry with values normalized for PostgreSQL/SQLite JSON columns."""
    db.add(
        AuditLog(
            brand_id=brand_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=jsonable_encoder(details or {}),
            ip_address=ip_address,
        )
    )
