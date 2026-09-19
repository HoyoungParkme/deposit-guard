import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { TopBar } from '../components/TopBar';
import { getCriteria } from '../api/client';

export const CriteriaPage: React.FC = () => {
  const [criteria, setCriteria] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'grades' | 'signals' | 'repayment' | 'checks'>('grades');

  useEffect(() => {
    getCriteria()
      .then((data) => setCriteria(data))
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <TopBar />

      <div className="max-w-4xl mx-auto w-full p-4 sm:p-6 lg:p-8 space-y-6">
        {/* 헤더 */}
        <div className="flex items-center justify-between border-b border-gray-200 pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Link to="/" className="hover:text-blue-600 transition">
                홈
              </Link>
              <span>/</span>
              <span className="font-semibold text-gray-900">판정 기준 공개</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-black text-gray-900">
              보증금지킴 권리분석 및 위험 판정 기준
            </h1>
          </div>

          <Link
            to="/"
            className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-4 py-2 rounded-xl shadow-sm transition"
          >
            내 등기부 검토하기
          </Link>
        </div>

        {/* 탭 네비게이션 */}
        <div className="flex border-b border-gray-200 gap-2 overflow-x-auto pb-px">
          {[
            { id: 'grades', label: '1. 위험 등급 기준' },
            { id: 'signals', label: '2. 위험 신호 11종' },
            { id: 'repayment', label: '3. 최우선변제금 기준표' },
            { id: 'checks', label: '4. 물건별 필수 점검' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2.5 text-xs font-bold rounded-t-xl transition border-b-2 whitespace-nowrap ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600 bg-white shadow-xs'
                  : 'border-transparent text-gray-500 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-xs text-gray-400 animate-pulse">
            기준표를 불러오는 중...
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-6">
            {/* 탭 1: 위험 등급 기준 */}
            {activeTab === 'grades' && (
              <div className="space-y-4">
                <div className="space-y-1">
                  <h2 className="text-sm font-bold text-gray-900">위험 등급 분류 기준 (LH 전세임대 권리분석 기준)</h2>
                  <p className="text-xs text-gray-500">
                    부채비율(집값 대비 근저당+선순위보증금+내 보증금)과 위험 신호 여부에 따라 3단계로 엄격하게 판정합니다.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                  <div className="bg-emerald-50/70 border border-emerald-200 rounded-2xl p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-extrabold text-emerald-800 px-2.5 py-1 bg-emerald-100 rounded-lg">
                        🟢 안전 (Safe)
                      </span>
                      <span className="text-xs font-bold text-emerald-900">부채비율 ≤ 70%</span>
                    </div>
                    <p className="text-xs text-emerald-950 leading-relaxed">
                      선순위 채권과 보증금의 합이 집값의 70% 이하이며, 압류·신탁·경매 등 위험 신호가 없는 정상적인 매물입니다.
                    </p>
                  </div>

                  <div className="bg-amber-50/70 border border-amber-200 rounded-2xl p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-extrabold text-amber-800 px-2.5 py-1 bg-amber-100 rounded-lg">
                        🟡 주의 (Caution)
                      </span>
                      <span className="text-xs font-bold text-amber-900">부채비율 70% ~ 90%</span>
                    </div>
                    <p className="text-xs text-amber-950 leading-relaxed">
                      부채비율이 다소 높거나 최근 근저당/잦은 소유권 이전 등 주의 신호가 있는 매물입니다. 전세보증보험 가입과 안전 특약이 필수입니다.
                    </p>
                  </div>

                  <div className="bg-rose-50/70 border border-rose-200 rounded-2xl p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-extrabold text-rose-800 px-2.5 py-1 bg-rose-100 rounded-lg">
                        🔴 위험 (Danger)
                      </span>
                      <span className="text-xs font-bold text-rose-900">부채비율 &gt; 90%</span>
                    </div>
                    <p className="text-xs text-rose-950 leading-relaxed">
                      집값의 90%를 초과하는 깡통전세이거나, 경매·압류·가등기·임차권등기명령 등 심각한 위험 신호가 확인되어 계약을 피해야 합니다.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* 탭 2: 위험 신호 11종 */}
            {activeTab === 'signals' && (
              <div className="space-y-4">
                <div className="space-y-1">
                  <h2 className="text-sm font-bold text-gray-900">탐지하는 11가지 부동산 위험 신호 (Red Flags)</h2>
                  <p className="text-xs text-gray-500">
                    등기부 갑구·을구 및 HUG 상습 채무불이행자 명단, 건축물대장을 통해 실시간 교차 검증합니다.
                  </p>
                </div>

                <div className="divide-y divide-gray-100">
                  {(criteria?.signals || [
                    { code: 'auction', severity: 'danger', label: '경매개시결정 등기', source: '민사집행법 제83조' },
                    { code: 'seizure', severity: 'danger', label: '압류·가압류·가처분 등기', source: '국세징수법 / 민사집행법' },
                    { code: 'leasehold_registration', severity: 'danger', label: '임차권등기명령 (보증금 미반환 이력)', source: '주택임대차보호법 제3조의3' },
                    { code: 'trust', severity: 'danger', label: '신탁 등기 (신탁원부 필요)', source: '신탁법 제4조' },
                    { code: 'defaulter', severity: 'danger', label: 'HUG 상습 채무불이행자(악성 임대인) 일치', source: '주택도시기금법 제24조' },
                    { code: 'recent_mortgage', severity: 'caution', label: '최근 2개월 내 설정된 신규 근저당', source: '전세사기 피해사례 패턴' },
                    { code: 'frequent_ownership_transfer', severity: 'caution', label: '최근 1년 내 2회 이상 소유권 이전 (바지사장 의심)', source: '국토교통부 전세사기 예방수칙' },
                    { code: 'illegal_building', severity: 'caution', label: '건축물대장 위반건축물 표기', source: '건축법 제79조' },
                    { code: 'multi_household_unregistered', severity: 'caution', label: '다가구주택 선순위 보증금 미확인', source: 'LH 권리분석 기준' },
                  ]).map((sig: any, sIdx: number) => (
                    <div key={sIdx} className="py-3 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                            sig.severity === 'danger' ? 'bg-rose-600 text-white' : 'bg-amber-600 text-white'
                          }`}
                        >
                          {sig.severity === 'danger' ? '위험' : '주의'}
                        </span>
                        <span className="text-xs font-bold text-gray-900">{sig.label}</span>
                      </div>
                      <span className="text-[11px] text-gray-400">{sig.source || '공식 기준'}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 탭 3: 최우선변제금 기준표 */}
            {activeTab === 'repayment' && (
              <div className="space-y-4">
                <div className="space-y-1">
                  <h2 className="text-sm font-bold text-gray-900">주택임대차보호법 소액임차인 최우선변제금 기준표</h2>
                  <p className="text-xs text-gray-500">
                    경매 시 다른 근저당권자보다 먼저 보장받을 수 있는 법정 최소 보증금 한도입니다. (2023년 최신 개정)
                  </p>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left border border-gray-200 rounded-xl overflow-hidden">
                    <thead className="bg-slate-50 text-gray-700 font-bold border-b border-gray-200">
                      <tr>
                        <th className="p-3">지역 구분</th>
                        <th className="p-3">보호 대상 보증금 한도</th>
                        <th className="p-3 text-blue-600">최우선 변제 보장액</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      <tr className="hover:bg-slate-50">
                        <td className="p-3 font-semibold text-gray-900">서울특별시</td>
                        <td className="p-3 text-gray-600">1억 6,500만원 이하</td>
                        <td className="p-3 font-bold text-blue-600">최대 5,500만원</td>
                      </tr>
                      <tr className="hover:bg-slate-50">
                        <td className="p-3 font-semibold text-gray-900">과밀억제권역 (인천·수원·성남 등), 세종, 용인, 화성, 김포</td>
                        <td className="p-3 text-gray-600">1억 4,500만원 이하</td>
                        <td className="p-3 font-bold text-blue-600">최대 4,800만원</td>
                      </tr>
                      <tr className="hover:bg-slate-50">
                        <td className="p-3 font-semibold text-gray-900">광역시 (부산·대구·광주·대전·울산 등), 안산, 광주, 파주 등</td>
                        <td className="p-3 text-gray-600">8,500만원 이하</td>
                        <td className="p-3 font-bold text-blue-600">최대 2,800만원</td>
                      </tr>
                      <tr className="hover:bg-slate-50">
                        <td className="p-3 font-semibold text-gray-900">그 밖의 지역</td>
                        <td className="p-3 text-gray-600">7,500만원 이하</td>
                        <td className="p-3 font-bold text-blue-600">최대 2,500만원</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 탭 4: 물건별 필수 점검 */}
            {activeTab === 'checks' && (
              <div className="space-y-4">
                <div className="space-y-1">
                  <h2 className="text-sm font-bold text-gray-900">물건 유형별 AI 에이전트 필수 점검 체크리스트</h2>
                  <p className="text-xs text-gray-500">
                    아파트, 다세대, 다가구 등 각 주택의 특성에 맞추어 에이전트가 점검하는 항목입니다.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="border border-gray-200 rounded-xl p-4 space-y-2">
                    <span className="text-xs font-bold text-blue-600">🏢 아파트 / 오피스텔</span>
                    <ul className="text-xs text-gray-600 space-y-1">
                      <li>• 동일 단지/면적 최근 6개월 실거래가 시세 확인</li>
                      <li>• 을구 근저당 채권최고액 합산 및 부채비율 계산</li>
                      <li>• 소유자 일치 여부 및 신탁 등기 유무 확인</li>
                    </ul>
                  </div>

                  <div className="border border-gray-200 rounded-xl p-4 space-y-2">
                    <span className="text-xs font-bold text-amber-600">🏡 신축 다세대 / 연립 (빌라)</span>
                    <ul className="text-xs text-gray-600 space-y-1">
                      <li>• 인근 유사 빌라 실거래가 추정 및 공시가격 대조</li>
                      <li>• 건축물대장상 위반건축물 표기 유무 검증</li>
                      <li>• 단기 소유권 변동 및 근저당 급증 여부 추적</li>
                    </ul>
                  </div>

                  <div className="border border-gray-200 rounded-xl p-4 space-y-2">
                    <span className="text-xs font-bold text-rose-600">🏘️ 다가구 / 단독주택</span>
                    <ul className="text-xs text-gray-600 space-y-1">
                      <li>• 건물 및 토지 등기부 2종 일치 여부 대조</li>
                      <li>• 다른 모든 세입자의 선순위 보증금 합산 검토</li>
                      <li>• 임차권등기명령 등 과거 분쟁 이력 확인</li>
                    </ul>
                  </div>

                  <div className="border border-gray-200 rounded-xl p-4 space-y-2">
                    <span className="text-xs font-bold text-indigo-600">🛡️ 공통 검증 절차</span>
                    <ul className="text-xs text-gray-600 space-y-1">
                      <li>• HUG 상습 채무불이행자(악성 임대인) 명단 실시간 대조</li>
                      <li>• 대리 계약 여부 및 인감증명서/위임장 검증 질문</li>
                      <li>• 전세보증보험 가입 요건 부합 여부 산출</li>
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
