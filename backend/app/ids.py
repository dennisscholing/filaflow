import secrets
import time
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session


def uuid7() -> uuid.UUID:
    """Generate an RFC 9562-compatible, time-sortable UUIDv7."""
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand = secrets.randbits(74)
    value = timestamp_ms << 80
    value |= 0x7 << 76
    value |= ((rand >> 62) & 0xFFF) << 64
    value |= 0b10 << 62
    value |= rand & ((1 << 62) - 1)
    return uuid.UUID(int=value)


def next_code(db: Session, model, prefix: str, width: int = 4) -> str:
    existing = db.scalars(select(model.code).where(model.code.like(f"{prefix}-%"))).all()
    highest = 0
    for code in existing:
        try:
            highest = max(highest, int(code.rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return f"{prefix}-{highest + 1:0{width}d}"
