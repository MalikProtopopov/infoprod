"""funnels module: lead_magnets, funnels, funnel_steps, funnel_entries,
funnel_triggers, scheduled_messages + ALTERS

Revision ID: 0050_funnels_module
Revises: 0040_payments_attribution
Create Date: 2026-05-23 02:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0050_funnels_module"
down_revision: Union[str, None] = "0040_payments_attribution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── lead_magnets ──
    op.create_table(
        "lead_magnets",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("file_url", sa.Text, nullable=False),
        sa.Column("file_type", sa.String(32), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("telegram_file_id", sa.Text, nullable=True),
        sa.Column("product_id", sa.BigInteger, sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("download_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("admins.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_lead_magnets_product",
        "lead_magnets", ["product_id"],
        postgresql_where=sa.text("product_id IS NOT NULL"),
    )
    op.create_index("idx_lead_magnets_active", "lead_magnets", ["is_active"])

    # ── funnels ──
    op.create_table(
        "funnels",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("product_id", sa.BigInteger,
                  sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bot_id", sa.BigInteger, sa.ForeignKey("bots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("ttl_days", sa.Integer, nullable=False, server_default="90"),
        sa.Column("cancel_on_payment", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("admins.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_funnels_product", "funnels", ["product_id"])
    op.create_index("idx_funnels_active", "funnels", ["is_active", "created_at"])

    # ── funnel_steps ──
    op.create_table(
        "funnel_steps",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("funnel_id", sa.BigInteger,
                  sa.ForeignKey("funnels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_idx", sa.Integer, nullable=False),
        sa.Column("delay_minutes", sa.Integer, nullable=False),
        sa.Column("message_text", sa.Text, nullable=False),
        sa.Column("parse_mode", sa.String(16), nullable=True, server_default="HTML"),
        sa.Column("lead_magnet_id", sa.BigInteger,
                  sa.ForeignKey("lead_magnets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("buttons", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_funnel_steps_funnel", "funnel_steps", ["funnel_id", "order_idx"])
    op.create_unique_constraint("idx_funnel_steps_order", "funnel_steps", ["funnel_id", "order_idx"])

    # ── funnel_entries ──
    op.create_table(
        "funnel_entries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("funnel_id", sa.BigInteger,
                  sa.ForeignKey("funnels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.BigInteger, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
    )
    op.create_index("idx_funnel_entries_user", "funnel_entries", ["user_id", "status"])
    op.create_index("idx_funnel_entries_funnel", "funnel_entries", ["funnel_id", "status"])
    op.create_index(
        "idx_funnel_entries_active", "funnel_entries", ["status", "started_at"],
        postgresql_where=sa.text("status = 'active'"),
    )
    # Один user не может быть одновременно в 2 активных entries одной воронки
    op.create_index(
        "idx_funnel_entries_unique_active", "funnel_entries", ["funnel_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    # ── funnel_triggers ──
    op.create_table(
        "funnel_triggers",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("word", sa.Text, nullable=False),
        sa.Column("funnel_id", sa.BigInteger,
                  sa.ForeignKey("funnels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("use_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute("CREATE UNIQUE INDEX idx_funnel_triggers_word ON funnel_triggers (lower(word))")
    op.create_index("idx_funnel_triggers_funnel", "funnel_triggers", ["funnel_id"])

    # ── scheduled_messages ──
    op.create_table(
        "scheduled_messages",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funnel_entry_id", sa.BigInteger,
                  sa.ForeignKey("funnel_entries.id", ondelete="CASCADE"), nullable=True),
        sa.Column("funnel_step_id", sa.BigInteger,
                  sa.ForeignKey("funnel_steps.id", ondelete="SET NULL"), nullable=True),
        sa.Column("template_key", sa.Text, nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_scheduled_due", "scheduled_messages", ["scheduled_at"],
        postgresql_where=sa.text("sent_at IS NULL AND cancelled_at IS NULL"),
    )
    op.create_index("idx_scheduled_user", "scheduled_messages", ["user_id", "scheduled_at"])
    op.create_index("idx_scheduled_funnel_entry", "scheduled_messages", ["funnel_entry_id"])

    # ── ALTERS ──
    op.add_column(
        "tracking_links",
        sa.Column("funnel_id", sa.BigInteger,
                  sa.ForeignKey("funnels.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("default_funnel_id", sa.BigInteger,
                  sa.ForeignKey("funnels.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("notifications_enabled", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("users", "notifications_enabled")
    op.drop_column("products", "default_funnel_id")
    op.drop_column("tracking_links", "funnel_id")

    op.drop_index("idx_scheduled_funnel_entry", table_name="scheduled_messages")
    op.drop_index("idx_scheduled_user", table_name="scheduled_messages")
    op.drop_index("idx_scheduled_due", table_name="scheduled_messages")
    op.drop_table("scheduled_messages")

    op.drop_index("idx_funnel_triggers_funnel", table_name="funnel_triggers")
    op.execute("DROP INDEX IF EXISTS idx_funnel_triggers_word")
    op.drop_table("funnel_triggers")

    op.drop_index("idx_funnel_entries_unique_active", table_name="funnel_entries")
    op.drop_index("idx_funnel_entries_active", table_name="funnel_entries")
    op.drop_index("idx_funnel_entries_funnel", table_name="funnel_entries")
    op.drop_index("idx_funnel_entries_user", table_name="funnel_entries")
    op.drop_table("funnel_entries")

    op.drop_constraint("idx_funnel_steps_order", "funnel_steps", type_="unique")
    op.drop_index("idx_funnel_steps_funnel", table_name="funnel_steps")
    op.drop_table("funnel_steps")

    op.drop_index("idx_funnels_active", table_name="funnels")
    op.drop_index("idx_funnels_product", table_name="funnels")
    op.drop_table("funnels")

    op.drop_index("idx_lead_magnets_active", table_name="lead_magnets")
    op.drop_index("idx_lead_magnets_product", table_name="lead_magnets")
    op.drop_table("lead_magnets")
