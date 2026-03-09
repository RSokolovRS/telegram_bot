from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.enums import (
    InvoiceStatus,
    PaymentProvider,
    PaymentStatus,
    ServerStatus,
    SubscriptionPlan,
    SubscriptionStatus,
    TicketAuthorRole,
    TicketStatus,
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(8), default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    trials: Mapped[list[Trial]] = relationship(back_populates="user")
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="user")
    vpn_accounts: Mapped[list[VpnAccount]] = relationship(back_populates="user")
    payments: Mapped[list[Payment]] = relationship(back_populates="user")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="user")
    ticket_threads: Mapped[list[TicketThread]] = relationship(back_populates="user")


class Trial(Base):
    __tablename__ = "trials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    notified_end: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_after_grace: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="trials")
    server: Mapped[Server] = relationship(back_populates="trials")


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    base_url: Mapped[str] = mapped_column(String(500))
    panel_path_prefix: Mapped[str] = mapped_column(String(64), default="/sub/")
    username: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(255))
    inbound_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[ServerStatus] = mapped_column(Enum(ServerStatus), default=ServerStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    trials: Mapped[list[Trial]] = relationship(back_populates="server")
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="server")
    vpn_accounts: Mapped[list[VpnAccount]] = relationship(back_populates="server")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="RESTRICT"), index=True)
    plan: Mapped[SubscriptionPlan] = mapped_column(Enum(SubscriptionPlan))
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    notified_expiry: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="subscriptions")
    server: Mapped[Server] = relationship(back_populates="subscriptions")


class VpnAccount(Base):
    __tablename__ = "vpn_accounts"
    __table_args__ = (UniqueConstraint("server_id", "sui_client_id", name="uq_vpn_server_client"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="RESTRICT"), index=True)
    sui_client_id: Mapped[str] = mapped_column(String(255), index=True)
    subscription_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="vpn_accounts")
    server: Mapped[Server] = relationship(back_populates="vpn_accounts")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[PaymentProvider] = mapped_column(Enum(PaymentProvider), index=True)
    provider_payment_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    amount_rub: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="payments")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (Index("ix_invoice_provider_external", "provider", "provider_invoice_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="RESTRICT"), index=True)
    subscription_plan: Mapped[SubscriptionPlan] = mapped_column(Enum(SubscriptionPlan))
    provider: Mapped[PaymentProvider] = mapped_column(Enum(PaymentProvider), index=True)
    provider_invoice_id: Mapped[str] = mapped_column(String(255), unique=True)
    amount_rub: Mapped[float] = mapped_column(Numeric(10, 2))
    amount_due_provider: Mapped[float | None] = mapped_column(Float, nullable=True)
    locked_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.CREATED)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="invoices")


class TicketThread(Base):
    __tablename__ = "ticket_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.OPEN, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="ticket_threads")
    messages: Mapped[list[TicketMessage]] = relationship(back_populates="thread")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("ticket_threads.id", ondelete="CASCADE"), index=True)
    author_role: Mapped[TicketAuthorRole] = mapped_column(Enum(TicketAuthorRole))
    author_telegram_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    thread: Mapped[TicketThread] = relationship(back_populates="messages")


class SchedulerLock(Base):
    __tablename__ = "scheduler_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lock_name: Mapped[str] = mapped_column(String(255), unique=True)
    locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


Index("ix_subscription_user_status", Subscription.user_id, Subscription.status)
Index("ix_trial_end_notified", Trial.ends_at, Trial.notified_end)
