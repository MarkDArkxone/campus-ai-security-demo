from sqlalchemy.orm import Session

from app.alarm_manager import alarm_manager
from app.models import AccessDevice, AccessRecord, Person, VisitorRecord
from app.schemas import AccessSimulateIn


async def simulate_access(db: Session, payload: AccessSimulateIn) -> AccessRecord:
    person = db.get(Person, payload.person_id)
    device = db.get(AccessDevice, payload.device_id)
    if not person or not device:
        raise ValueError("Person or device not found")

    denied = person.status == "blacklist" or person.role == "blacklist"
    record = AccessRecord(
        person_id=person.id,
        device_id=device.id,
        access_type=payload.access_type,
        auth_method=payload.auth_method,
        result="denied" if denied else "allowed",
        message="Blacklist denied" if denied else "Access allowed",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    if denied:
        await alarm_manager.create_alarm(
            "access_denied",
            "high",
            f"Blacklist person {person.name} attempted to pass {device.name}",
            person_count=1,
            location=device.location,
        )
    return record


async def simulate_visitor_entry(db: Session, visitor_id: int, device_id: int | None = None) -> AccessRecord:
    visitor = db.get(VisitorRecord, visitor_id)
    if not visitor:
        raise ValueError("Visitor not found")
    if visitor.status != "approved":
        result = "denied"
        message = "Visitor is not approved"
    else:
        result = "allowed"
        message = "Visitor access allowed"

    device = db.get(AccessDevice, device_id) if device_id else db.query(AccessDevice).first()
    record = AccessRecord(
        person_id=None,
        device_id=device.id if device else None,
        access_type="entry",
        auth_method="manual",
        result=result,
        message=f"{visitor.visitor_name}: {message}",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
