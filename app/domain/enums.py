from __future__ import annotations

from enum import Enum


class ServerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class SubscriptionPlan(str, Enum):
    MONTH = "month"
    YEAR = "year"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELED = "canceled"


class PaymentProvider(str, Enum):
    YOOKASSA = "yookassa"
    CRYPTO = "crypto"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"
    FAILED = "failed"


class InvoiceStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"
    EXPIRED = "expired"


class TicketStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class TicketAuthorRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
