"""ORM 모델 15개 정의 및 메타데이터 검증 테스트.

근거: JSD-DOM-002 2장, JSD-DOM-003 1~3장
"""

from app.core.db import Base
# 모든 모델 로드
import app.domains.review.models  # noqa: F401
import app.domains.registry.models  # noqa: F401
import app.domains.citation.models  # noqa: F401
import app.domains.report.models  # noqa: F401
import app.domains.share.models  # noqa: F401
import app.domains.lookup.models  # noqa: F401
import app.domains.gate.models  # noqa: F401


EXPECTED_TABLES = {
    "reviews",
    "review_records",
    "questions",
    "follow_up_turns",
    "usage_logs",
    "registry_extracts",
    "registry_entries",
    "citations",
    "opinions",
    "shared_opinions",
    "defaulter_records",
    "region_codes",
    "lookup_caches",
    "ip_quotas",
    "file_caches",
}


def test_all_15_tables_registered():
    """테스트 관점: 15개 테이블이 모두 SQLAlchemy Base.metadata에 등록되어 있는가."""
    registered = set(Base.metadata.tables.keys())
    assert registered == EXPECTED_TABLES, f"누락되거나 잘못된 테이블: {EXPECTED_TABLES.symmetric_difference(registered)}"


def test_table_columns():
    """테스트 관점: 주요 테이블 컬럼 존재 및 타입 기본 검증."""
    reviews_table = Base.metadata.tables["reviews"]
    assert "id" in reviews_table.c
    assert "deposit_manwon" in reviews_table.c
    assert "facts" in reviews_table.c

    entries_table = Base.metadata.tables["registry_entries"]
    assert "purpose_code" in entries_table.c
    assert "block_ids" in entries_table.c
    assert "cancelled" in entries_table.c
