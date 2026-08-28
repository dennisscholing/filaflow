import uuid
from sqlalchemy.orm import Session
from .models import AuditEvent, User


def audit(db: Session, user: User | None, action: str, entity_type: str, entity_id: uuid.UUID | None, details: dict | None = None) -> None:
    db.add(AuditEvent(actor_id=user.id if user else None, action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}))
