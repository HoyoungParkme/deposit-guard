"""0001_initial: 15개 테이블 생성, 제약조건, 외래키, 인덱스.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-18
근거: JSD-DOM-003 1장, 2장, 3장
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PURPOSE_CODES_SQL = (
    "'ownership_preserve', 'ownership_transfer', 'mortgage', 'mortgage_change', "
    "'jeonse_right', 'lease_right', 'seizure', 'provisional_seizure', 'injunction', "
    "'provisional_registration', 'auction', 'trust', 'notice_registration', "
    "'cancellation', 'other'"
)


def upgrade() -> None:
    # 1. reviews
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="created"),
        sa.Column("deposit_manwon", sa.Integer(), nullable=False),
        sa.Column("contract_type", sa.Text(), nullable=False),
        sa.Column("counterparty_name", sa.Text(), nullable=True),
        sa.Column("sample_id", sa.Text(), nullable=True),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parsed_pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_krw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_cost_krw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("corrections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('created', 'running', 'waiting_user', 'done', 'failed', 'expired')",
            name="ck_reviews_status",
        ),
        sa.CheckConstraint(
            "contract_type IN ('jeonse', 'monthly')",
            name="ck_reviews_contract_type",
        ),
    )
    # JSD-DOM-003: (expires_at) where status <> 'expired' 부분
    op.create_index(
        "ix_reviews_expires_at_active",
        "reviews",
        ["expires_at"],
        postgresql_where=sa.text("status <> 'expired'"),
    )

    # 2. follow_up_turns
    op.create_table(
        "follow_up_turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'done', 'failed')",
            name="ck_follow_up_turns_status",
        ),
    )
    op.create_index(
        "ix_follow_up_turns_review_status",
        "follow_up_turns",
        ["review_id", "status"],
    )
    # JSD-DOM-003: (review_id) where status = 'running' 부분 unique
    op.create_index(
        "uq_follow_up_turns_running",
        "follow_up_turns",
        ["review_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    # 3. review_records
    op.create_table(
        "review_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "turn_id",
            sa.Integer(),
            sa.ForeignKey("follow_up_turns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("review_id", "seq", name="uq_review_records_review_seq"),
        sa.CheckConstraint(
            "role IN ('agent', 'user', 'system')",
            name="ck_review_records_role",
        ),
        sa.CheckConstraint(
            "kind IN ('say', 'tool', 'question', 'answer', 'numbers', 'report', 'notice', 'error')",
            name="ck_review_records_kind",
        ),
    )
    op.create_index(
        "ix_review_records_turn_id",
        "review_records",
        ["turn_id"],
        postgresql_where=sa.text("turn_id IS NOT NULL"),
    )

    # 4. questions
    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asked_no", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("why", sa.Text(), nullable=False),
        sa.Column("input_type", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("help_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answer_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('illegal_building', 'price', 'tenants', 'proxy', 'owner_type', 'land_registry', 'other')",
            name="ck_questions_kind",
        ),
        sa.CheckConstraint(
            "input_type IN ('choice', 'number', 'text', 'file')",
            name="ck_questions_input_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'answered', 'timeout')",
            name="ck_questions_status",
        ),
    )
    op.create_index(
        "ix_questions_review_status",
        "questions",
        ["review_id", "status"],
    )

    # 5. usage_logs
    op.create_table(
        "usage_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("is_sample", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parsed_pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_krw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("corrections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_fallback", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('created', 'running', 'waiting_user', 'done', 'failed', 'expired')",
            name="ck_usage_logs_status",
        ),
    )
    op.create_index(
        "ix_usage_logs_updated_at",
        "usage_logs",
        ["updated_at"],
    )

    # 6. registry_extracts
    op.create_table(
        "registry_extracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("file_sha256", sa.Text(), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("lot_address", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("building_type", sa.Text(), nullable=True),
        sa.Column("land_right_unregistered", sa.Boolean(), nullable=True),
        sa.Column("separate_land_registry", sa.Boolean(), nullable=True),
        sa.Column("exclusive_area_m2", sa.Float(), nullable=True),
        sa.Column("building_name", sa.Text(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("read_by_agent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id", "review_id", name="uq_registry_extracts_id_review"),
        sa.CheckConstraint(
            "kind IN ('building', 'land', 'collective')",
            name="ck_registry_extracts_kind",
        ),
        sa.CheckConstraint(
            "building_type IS NULL OR building_type IN ('apartment', 'multi_family_unit', 'multi_household', 'officetel', 'other')",
            name="ck_registry_extracts_building_type",
        ),
    )
    op.create_index(
        "ix_registry_extracts_review_id",
        "registry_extracts",
        ["review_id"],
    )

    # 7. registry_entries
    op.create_table(
        "registry_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("extract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_id", sa.Text(), nullable=False),
        sa.Column("section", sa.Text(), nullable=False),
        sa.Column("rank_no", sa.Text(), nullable=False),
        sa.Column("parent_entry_id", sa.Text(), nullable=True),
        sa.Column("purpose_code", sa.Text(), nullable=False),
        sa.Column("purpose_text", sa.Text(), nullable=False),
        sa.Column("received_at", sa.Date(), nullable=True),
        sa.Column("receipt_no", sa.Text(), nullable=True),
        sa.Column("cause", sa.Text(), nullable=True),
        sa.Column("amount_manwon", sa.Integer(), nullable=True),
        sa.Column("price_manwon", sa.Integer(), nullable=True),
        sa.Column("holder", sa.Text(), nullable=True),
        sa.Column("holder_is_corporation", sa.Boolean(), nullable=True),
        sa.Column("cancelled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cancelled_by_entry_id", sa.Text(), nullable=True),
        sa.Column("block_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("location_label", sa.Text(), nullable=False),
        sa.UniqueConstraint("review_id", "entry_id", name="uq_registry_entries_review_entry"),
        sa.ForeignKeyConstraint(
            ["extract_id", "review_id"],
            ["registry_extracts.id", "registry_extracts.review_id"],
            ondelete="CASCADE",
            name="fk_registry_entries_extract",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "parent_entry_id"],
            ["registry_entries.review_id", "registry_entries.entry_id"],
            ondelete="CASCADE",
            name="fk_registry_entries_parent",
        ),
        sa.CheckConstraint(
            "section IN ('gap', 'eul')",
            name="ck_registry_entries_section",
        ),
        sa.CheckConstraint(
            f"purpose_code IN ({PURPOSE_CODES_SQL})",
            name="ck_registry_entries_purpose_code",
        ),
    )
    op.create_index(
        "ix_registry_entries_extract_id",
        "registry_entries",
        ["extract_id"],
    )
    op.create_index(
        "ix_registry_entries_parent",
        "registry_entries",
        ["review_id", "parent_entry_id"],
        postgresql_where=sa.text("parent_entry_id IS NOT NULL"),
    )

    # 8. citations
    op.create_table(
        "citations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("used_in", sa.Text(), nullable=False),
        sa.Column("ref", sa.Text(), nullable=False, server_default=""),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("usage_label", sa.Text(), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("block_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "used_in IN ('message', 'conclusion', 'rights', 'signal', 'checked', 'clause')",
            name="ck_citations_used_in",
        ),
    )
    op.create_index(
        "ix_citations_review_used_ref",
        "citations",
        ["review_id", "used_in", "ref"],
    )

    # 9. opinions
    op.create_table(
        "opinions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("subject", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("revision_reason", sa.Text(), nullable=True),
        sa.Column("written_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 10. shared_opinions
    op.create_table(
        "shared_opinions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.Text(), nullable=False, unique=True),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("subject", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_shared_opinions_expires_active",
        "shared_opinions",
        ["expires_at"],
        postgresql_where=sa.text("report IS NOT NULL"),
    )

    # 11. defaulter_records
    op.create_table(
        "defaulter_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("debt_manwon", sa.Integer(), nullable=True),
        sa.Column("default_period", sa.Text(), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
    )
    op.execute(
        "CREATE INDEX ix_defaulter_records_clean_name ON defaulter_records ((regexp_replace(name, '\\s', '', 'g')))"
    )

    # 12. region_codes
    op.create_table(
        "region_codes",
        sa.Column("code", sa.CHAR(10), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )

    # 13. lookup_caches
    op.create_table(
        "lookup_caches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('trade', 'building')",
            name="ck_lookup_caches_kind",
        ),
    )

    # 14. ip_quotas
    op.create_table(
        "ip_quotas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ip_hash", sa.Text(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("ip_hash", "day", name="uq_ip_quotas_hash_day"),
    )

    # 15. file_caches
    op.create_table(
        "file_caches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("file_sha256", sa.Text(), nullable=False, unique=True),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("file_caches")
    op.drop_table("ip_quotas")
    op.drop_table("lookup_caches")
    op.drop_table("region_codes")
    op.execute("DROP INDEX IF EXISTS ix_defaulter_records_clean_name")
    op.drop_table("defaulter_records")
    op.drop_table("shared_opinions")
    op.drop_table("opinions")
    op.drop_table("citations")
    op.drop_table("registry_entries")
    op.drop_table("registry_extracts")
    op.drop_table("usage_logs")
    op.drop_table("questions")
    op.drop_table("review_records")
    op.drop_table("follow_up_turns")
    op.drop_table("reviews")
