"""PaymentAttempt and MerchantOrder domain models (spec sections 3.2-3.3)."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from .enums import OrderStatus


class PaymentAttempt(BaseModel):
    payment_attempt_id: str
    transaction_ref: str
    merchant_order_ref: Optional[str] = None
    amount: Decimal
    currency: str = "INR"
    payment_method: str
    created_at: datetime

    # Preserved verbatim from the source system. Never silently translated into
    # a confirmed outcome — that interpretation is reconciliation's job (Phase 2).
    provider_status: str
    source_system: str
    correlation_ids: list[str] = Field(default_factory=list)


class MerchantOrder(BaseModel):
    order_id: str
    merchant_id: str
    payment_attempt_id: Optional[str] = None
    transaction_ref: Optional[str] = None
    amount: Decimal
    currency: str = "INR"

    # NOT_FOUND means the queried source had no matching record. It is not
    # evidence that the order never existed.
    order_status: OrderStatus
    created_at: datetime
    updated_at: datetime
    source_system: str
    raw_record_ref: Optional[str] = None
