"""Sample 도메인 서비스 (SampleService).

근거: JSD-DOM-002 4.10, JSD-MS-010, JSD-API-001, JSD-UC-001
"""

import json
from pathlib import Path

from app.core.errors import AppError
from app.domains.sample.schemas import SampleCase
from app.shared.types import ContractType, GradeLevel, Upload


def _get_samples_dir() -> Path:
    """assets/samples 디렉터리 경로를 반환한다."""
    # backend/app/domains/sample/service.py 기준 상위 4단계: deposit-guard root
    root = Path(__file__).resolve().parents[4]
    candidates = [
        root / "assets" / "samples",
        Path("assets/samples").resolve(),
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


class SampleService:
    """예시 등기부 사례 목록 및 파일 제공 서비스."""

    _cached_cases: list[SampleCase] | None = None

    @classmethod
    def list(cls) -> list[SampleCase]:
        """예시 카드 목록.

        항목 ID: JSD-MS-010#SampleService.list
        근거: JSD-API-001#GET/api/samples, JSD-UC-001#UC-A2 1, JSD-UI-001#UI-1
        """
        if cls._cached_cases is not None:
            return cls._cached_cases

        samples_dir = _get_samples_dir()
        json_path = samples_dir / "samples.json"
        if not json_path.exists():
            cls._cached_cases = []
            return cls._cached_cases

        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        cases: list[SampleCase] = []
        for item in raw_data:
            case = SampleCase(
                sample_id=item["sample_id"],
                title=item["title"],
                summary=item["summary"],
                region=item["region"],
                deposit_manwon=int(item["deposit_manwon"]),
                contract_type=ContractType(item["contract_type"]),
                file_name=item["file_name"],
                land_file_name=item.get("land_file_name"),
                expected_grade=GradeLevel(item["expected_grade"]),
            )
            cases.append(case)

        cls._cached_cases = cases
        return cls._cached_cases

    @classmethod
    def file(cls, sample_id: str) -> Upload:
        """예시 PDF를 업로드처럼.

        항목 ID: JSD-MS-010#SampleService.file
        근거: JSD-SEQ-001#SEQ-1, JSD-SEQ-001#SEQ-18, JSD-UC-001#UC-A2 2~3
        """
        cases = cls.list()
        target = next((c for c in cases if c.sample_id == sample_id), None)
        if target is None:
            raise AppError("missing_input", field="sample_id")

        samples_dir = _get_samples_dir()
        file_path = samples_dir / target.file_name
        if not file_path.exists():
            raise AppError("missing_input", field="sample_id")

        data = file_path.read_bytes()
        return Upload(
            data=data,
            media_type="application/pdf",
            filename=target.file_name,
        )

    @classmethod
    def fixture_html(cls, sample_id: str) -> str | None:
        """예시 HTML 사전 파싱 결과물 조회 (캐시 웜업 및 폴백용)."""
        samples_dir = _get_samples_dir()
        html_path = samples_dir / f"{sample_id}.html"
        if html_path.exists():
            return html_path.read_text(encoding="utf-8")
        return None
