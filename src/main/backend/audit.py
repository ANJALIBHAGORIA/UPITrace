"""Audit logging helper (spec section 3.10). All mutating backend operations
go through here. AuditRecord's own validator already rejects secret-like
metadata keys, so this is mostly bookkeeping (ID generation, timestamping).
"""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from typing import Any, Optional

from src.main.backend.models import AuditRecord, ExecutionMode
from src.main.backend.store import InMemoryStore

_counter = count(1)


def record(
    store: InMemoryStore,
    *,
    incident_id: str,
    actor_id: str,
    event_type: str,
    result: str,
    input_reference: Optional[str] = None,
    output_reference: Optional[str] = None,
    execution_mode: ExecutionMode = ExecutionMode.SIMULATED,
    metadata: Optional[dict[str, Any]] = None,
) -> AuditRecord:
    entry = AuditRecord(
        audit_record_id=f"AUD-{next(_counter):06d}",
        incident_id=incident_id,
        actor_id=actor_id,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        input_reference=input_reference,
        output_reference=output_reference,
        execution_mode=execution_mode,
        result=result,
        metadata=metadata or {},
    )
    store.audit_records.append(entry)
    return entry
