"""initial schema

Revision ID: 20260307_0001
Revises: 
Create Date: 2026-03-07 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    server_status = postgresql.ENUM("ACTIVE", "INACTIVE", name="serverstatus", create_type=False)
    subscription_plan = postgresql.ENUM("MONTH", "YEAR", name="subscriptionplan", create_type=False)
    subscription_status = postgresql.ENUM(
        "ACTIVE", "EXPIRED", "CANCELED", name="subscriptionstatus", create_type=False
    )
    payment_provider = postgresql.ENUM("YOOKASSA", "CRYPTO", name="paymentprovider", create_type=False)
    payment_status = postgresql.ENUM(
        "PENDING", "SUCCEEDED", "CANCELED", "FAILED", name="paymentstatus", create_type=False
    )
    invoice_status = postgresql.ENUM(
        "CREATED", "PENDING", "PAID", "CANCELED", "EXPIRED", name="invoicestatus", create_type=False
    )
    ticket_status = postgresql.ENUM("OPEN", "CLOSED", name="ticketstatus", create_type=False)
    ticket_author_role = postgresql.ENUM("USER", "ADMIN", name="ticketauthorrole", create_type=False)

    bind = op.get_bind()
    server_status.create(bind, checkfirst=True)
    subscription_plan.create(bind, checkfirst=True)
    subscription_status.create(bind, checkfirst=True)
    payment_provider.create(bind, checkfirst=True)
    payment_status.create(bind, checkfirst=True)
    invoice_status.create(bind, checkfirst=True)
    ticket_status.create(bind, checkfirst=True)
    ticket_author_role.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=8), nullable=False, server_default="ru"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("panel_path_prefix", sa.String(length=64), nullable=False, server_default="/sub/"),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("inbound_id", sa.Integer(), nullable=False),
        sa.Column("status", server_status, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "scheduler_locks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lock_name", sa.String(length=255), unique=True, nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scheduler_locks_locked_until", "scheduler_locks", ["locked_until"], unique=False)

    op.create_table(
        "trials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_after_grace", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("user_id", name="uq_trial_user"),
    )
    op.create_index("ix_trials_ends_at", "trials", ["ends_at"], unique=False)
    op.create_index("ix_trial_end_notified", "trials", ["ends_at", "notified_end"], unique=False)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan", subscription_plan, nullable=False),
        sa.Column("status", subscription_status, nullable=False, server_default="ACTIVE"),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_expiry", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=False)
    op.create_index("ix_subscriptions_server_id", "subscriptions", ["server_id"], unique=False)
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"], unique=False)
    op.create_index("ix_subscriptions_ends_at", "subscriptions", ["ends_at"], unique=False)
    op.create_index(
        "ix_subscription_user_status", "subscriptions", ["user_id", "status"], unique=False
    )

    op.create_table(
        "vpn_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sui_client_id", sa.String(length=255), nullable=False),
        sa.Column("subscription_url", sa.String(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("server_id", "sui_client_id", name="uq_vpn_server_client"),
    )
    op.create_index("ix_vpn_accounts_user_id", "vpn_accounts", ["user_id"], unique=False)
    op.create_index("ix_vpn_accounts_server_id", "vpn_accounts", ["server_id"], unique=False)
    op.create_index("ix_vpn_accounts_sui_client_id", "vpn_accounts", ["sui_client_id"], unique=False)
    op.create_index("ix_vpn_accounts_is_active", "vpn_accounts", ["is_active"], unique=False)

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", payment_provider, nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=False),
        sa.Column("amount_rub", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", payment_status, nullable=False, server_default="PENDING"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider_payment_id", name="uq_payment_provider_payment"),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_idempotency"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"], unique=False)
    op.create_index("ix_payments_provider", "payments", ["provider"], unique=False)
    op.create_index("ix_payments_provider_payment_id", "payments", ["provider_payment_id"], unique=False)

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subscription_plan", subscription_plan, nullable=False),
        sa.Column("provider", payment_provider, nullable=False),
        sa.Column("provider_invoice_id", sa.String(length=255), nullable=False),
        sa.Column("amount_rub", sa.Numeric(10, 2), nullable=False),
        sa.Column("amount_due_provider", sa.Float(), nullable=True),
        sa.Column("locked_rate", sa.Float(), nullable=True),
        sa.Column("status", invoice_status, nullable=False, server_default="CREATED"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider_invoice_id", name="uq_invoice_provider_invoice"),
    )
    op.create_index("ix_invoices_user_id", "invoices", ["user_id"], unique=False)
    op.create_index("ix_invoices_server_id", "invoices", ["server_id"], unique=False)
    op.create_index("ix_invoices_provider", "invoices", ["provider"], unique=False)
    op.create_index(
        "ix_invoice_provider_external", "invoices", ["provider", "provider_invoice_id"], unique=False
    )

    op.create_table(
        "ticket_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", ticket_status, nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ticket_threads_user_id", "ticket_threads", ["user_id"], unique=False)
    op.create_index("ix_ticket_threads_status", "ticket_threads", ["status"], unique=False)

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "thread_id", sa.Integer(), sa.ForeignKey("ticket_threads.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("author_role", ticket_author_role, nullable=False),
        sa.Column("author_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ticket_messages_thread_id", "ticket_messages", ["thread_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ticket_messages_thread_id", table_name="ticket_messages")
    op.drop_table("ticket_messages")

    op.drop_index("ix_ticket_threads_status", table_name="ticket_threads")
    op.drop_index("ix_ticket_threads_user_id", table_name="ticket_threads")
    op.drop_table("ticket_threads")

    op.drop_index("ix_invoice_provider_external", table_name="invoices")
    op.drop_index("ix_invoices_provider", table_name="invoices")
    op.drop_index("ix_invoices_server_id", table_name="invoices")
    op.drop_index("ix_invoices_user_id", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_payments_provider_payment_id", table_name="payments")
    op.drop_index("ix_payments_provider", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index("ix_vpn_accounts_is_active", table_name="vpn_accounts")
    op.drop_index("ix_vpn_accounts_sui_client_id", table_name="vpn_accounts")
    op.drop_index("ix_vpn_accounts_server_id", table_name="vpn_accounts")
    op.drop_index("ix_vpn_accounts_user_id", table_name="vpn_accounts")
    op.drop_table("vpn_accounts")

    op.drop_index("ix_subscription_user_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_ends_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_server_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_trial_end_notified", table_name="trials")
    op.drop_index("ix_trials_ends_at", table_name="trials")
    op.drop_table("trials")

    op.drop_index("ix_scheduler_locks_locked_until", table_name="scheduler_locks")
    op.drop_table("scheduler_locks")

    op.drop_table("servers")

    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    sa.Enum(name="ticketauthorrole").drop(bind, checkfirst=True)
    sa.Enum(name="ticketstatus").drop(bind, checkfirst=True)
    sa.Enum(name="invoicestatus").drop(bind, checkfirst=True)
    sa.Enum(name="paymentstatus").drop(bind, checkfirst=True)
    sa.Enum(name="paymentprovider").drop(bind, checkfirst=True)
    sa.Enum(name="subscriptionstatus").drop(bind, checkfirst=True)
    sa.Enum(name="subscriptionplan").drop(bind, checkfirst=True)
    sa.Enum(name="serverstatus").drop(bind, checkfirst=True)
