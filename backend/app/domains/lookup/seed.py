"""Lookup 초기 시드 데이터 적재기 (법정동코드 및 HUG 안심전세 악성 임대인 명단 스냅샷)."""

from datetime import date
import logging
from sqlalchemy import select, func
from app.core.db import async_session_factory
from app.domains.lookup.models import DefaulterRecord, RegionCode

logger = logging.getLogger(__name__)

INITIAL_REGION_CODES = [
    # 서울특별시 강서구
    ("1150010300", "서울특별시 강서구 화곡동"),
    ("1150010100", "서울특별시 강서구 염창동"),
    ("1150010200", "서울특별시 강서구 등촌동"),
    ("1150010400", "서울특별시 강서구 가양동"),
    ("1150010500", "서울특별시 강서구 마곡동"),
    ("1150010600", "서울특별시 강서구 내발산동"),
    ("1150010700", "서울특별시 강서구 외발산동"),
    ("1150010800", "서울특별시 강서구 공항동"),
    ("1150010900", "서울특별시 강서구 방화동"),
    ("1150011000", "서울특별시 강서구 개화동"),
    # 서울특별시 노원구
    ("1135010500", "서울특별시 노원구 상계동"),
    ("1135010600", "서울특별시 노원구 중계동"),
    ("1135010700", "서울특별시 노원구 하계동"),
    ("1135010300", "서울특별시 노원구 공릉동"),
    ("1135010200", "서울특별시 노원구 월계동"),
    # 서울특별시 관악구 / 동작구
    ("1162010100", "서울특별시 관악구 봉천동"),
    ("1162010200", "서울특별시 관악구 신림동"),
    ("1159010700", "서울특별시 동작구 사당동"),
    ("1159010800", "서울특별시 동작구 대방동"),
    ("1159010900", "서울특별시 동작구 신대방동"),
    # 서울특별시 마포구 / 서대문구 / 은평구
    ("1144012000", "서울특별시 마포구 서교동"),
    ("1144012100", "서울특별시 마포구 동교동"),
    ("1144012300", "서울특별시 마포구 망원동"),
    ("1144012400", "서울특별시 마포구 연남동"),
    ("1144010200", "서울특별시 마포구 공덕동"),
    ("1141011800", "서울특별시 서대문구 홍제동"),
    ("1138010300", "서울특별시 은평구 불광동"),
    ("1138010400", "서울특별시 은평구 갈현동"),
    # 서울특별시 강남구 / 서초구 / 송파구
    ("1168010100", "서울특별시 강남구 역삼동"),
    ("1168010300", "서울특별시 강남구 개포동"),
    ("1168010600", "서울특별시 강남구 대치동"),
    ("1165010800", "서울특별시 서초구 서초동"),
    ("1165010700", "서울특별시 서초구 반포동"),
    ("1171010100", "서울특별시 송파구 잠실동"),
    ("1171010200", "서울특별시 송파구 신천동"),
    ("1171010800", "서울특별시 송파구 문정동"),
    # 경기도 부천시
    ("4119210100", "경기도 부천시 원미구 심곡동"),
    ("4119210100", "경기도 부천시 심곡동"),
    ("4119210900", "경기도 부천시 중동"),
    ("4119211000", "경기도 부천시 상동"),
    ("4119010100", "경기도 부천시 원미동"),
    # 경기도 성남시 / 수원시 / 안양시
    ("4113510900", "경기도 성남시 분당구 삼평동"),
    ("4113510200", "경기도 성남시 분당구 정자동"),
    ("4111710200", "경기도 수원시 영통구 이의동"),
    ("4117310300", "경기도 안양시 동안구 관양동"),
    # 인천광역시
    ("2823710100", "인천광역시 부평구 부평동"),
    ("2820010100", "인천광역시 남동구 구월동"),
]

async def ensure_lookup_seed_data():
    """앱 시작 시 기본 법정동코드 및 악성 임대인 명단 스냅샷을 적재한다."""
    try:
        async with async_session_factory() as session:
            # 1. 법정동코드 적재
            rc_count = await session.scalar(select(func.count(RegionCode.code)))
            if not rc_count or rc_count == 0:
                logger.info("법정동코드 기본 데이터 적재 중 (%d건)...", len(INITIAL_REGION_CODES))
                for code, name in INITIAL_REGION_CODES:
                    session.add(RegionCode(code=code, name=name, is_active=True))
                await session.commit()
                logger.info("법정동코드 기본 데이터 적재 완료")

            # 2. 악성 임대인 명단 스냅샷 기본 등록 (HUG 공개 명단)
            def_count = await session.scalar(select(func.count(DefaulterRecord.id)))
            if not def_count or def_count == 0:
                logger.info("HUG 악성 임대인 공개 명단 초기 스냅샷 등록 중...")
                sample_defaulters = [
                    ("악성임대인1", "1970-01-01", 500000000, 5),
                    ("전세사기범", "1982-05-12", 850000000, 8),
                ]
                today_d = date(2026, 9, 1)
                for name, bday, debt, cnt in sample_defaulters:
                    session.add(
                        DefaulterRecord(
                            name=name,
                            birth_date=bday,
                            debt_amount=debt,
                            case_count=cnt,
                            snapshot_date=today_d,
                        )
                    )
                await session.commit()
                logger.info("HUG 악성 임대인 스냅샷 등록 완료")
    except Exception as exc:
        logger.warning("기본 시드 데이터 적재 실패 (계속 진행): %s", exc)
