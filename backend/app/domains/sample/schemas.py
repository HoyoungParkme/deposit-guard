"""Sample 도메인 스키마.

근거: JSD-DOM-002 2.8 SampleCase, JSD-MS-010
"""

from dataclasses import dataclass
from pydantic import BaseModel
from app.shared.types import ContractType, GradeLevel


@dataclass(frozen=True)
class SampleCase:
    """예시 사례 DTO (JSD-DOM-002 2.8 SampleCase)."""

    sample_id: str
    title: str
    summary: str
    region: str
    deposit_manwon: int
    contract_type: ContractType
    file_name: str
    land_file_name: str | None
    expected_grade: GradeLevel


class SampleCaseResponse(BaseModel):
    """GET /api/samples 응답 모델 (JSD-API-001 3장).

    내부 필드(file_name, land_file_name, expected_grade)는 제외된다.
    """

    sample_id: str
    title: str
    summary: str
    region: str
    deposit_manwon: int
    contract_type: ContractType
