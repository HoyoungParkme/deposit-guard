import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { TopBar } from '../components/TopBar';
import {
  ReportData,
  ReviewView,
  getReport,
  getReview,
  overrideValues,
  createShareLink,
  ApiError,
} from '../api/client';

export const ReportPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const [review, setReview] = useState<ReviewView | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // 시세/금액 직접 수정 폼 상태
  const [isOverrideOpen, setIsOverrideOpen] = useState<boolean>(false);
  const [overridePrice, setOverridePrice] = useState<string>('');
  const [isOverriding, setIsOverriding] = useState<boolean>(false);

  // 공유 모달 상태
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [isSharing, setIsSharing] = useState<boolean>(false);
  const [copySuccess, setCopySuccess] = useState<string | null>(null);

  // 체크리스트 로컬 체크 상태
  const [checkedTodos, setCheckedTodos] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);

    Promise.all([getReview(id), getReport(id)])
      .then(([revData, repData]) => {
        setReview(revData);
        setReport(repData);
        if (repData.price_manwon) {
          setOverridePrice(repData.price_manwon.toString());
        }
      })
      .catch((err) => {
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError('의견서를 불러오는 데 실패했습니다.');
        }
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [id]);

  // 시세 직접 수정 제출
  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || isOverriding) return;

    setIsOverriding(true);
    try {
      const priceNum = overridePrice ? parseInt(overridePrice, 10) : null;
      const updated = await overrideValues(id, {
        price_manwon: priceNum,
      });
      setReport(updated);
      setIsOverrideOpen(false);
      alert('시세가 반영되어 위험도와 부채비율이 재판정되었습니다.');
    } catch (err: any) {
      alert(err?.detail || '수정 반영에 실패했습니다.');
    } finally {
      setIsOverriding(false);
    }
  };

  // 공유 링크 생성
  const handleCreateShare = async () => {
    if (!id || isSharing) return;
    setIsSharing(true);
    try {
      const res = await createShareLink(id);
      const fullUrl = `${window.location.origin}${res.url}`;
      setShareUrl(fullUrl);
      await navigator.clipboard.writeText(fullUrl);
      setCopySuccess('공유 링크가 클립보드에 복사되었습니다! (7일간 유효)');
      setTimeout(() => setCopySuccess(null), 4000);
    } catch (err: any) {
      alert(err?.detail || '공유 링크 생성에 실패했습니다.');
    } finally {
      setIsSharing(false);
    }
  };

  // 특약사항 복사
  const handleCopyClause = async (clauseText: string, title: string) => {
    try {
      await navigator.clipboard.writeText(clauseText);
      setCopySuccess(`"${title}" 특약 문구가 복사되었습니다.`);
      setTimeout(() => setCopySuccess(null), 3000);
    } catch {
      alert('복사에 실패했습니다.');
    }
  };

  // 할 일 체크 토글
  const toggleTodo = (todoKey: string) => {
    setCheckedTodos((prev) => ({
      ...prev,
      [todoKey]: !prev[todoKey],
    }));
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <span className="text-3xl animate-spin">⏳</span>
          <p className="text-sm font-semibold text-gray-700">보증금 진단 의견서를 불러오는 중...</p>
          <p className="text-xs text-gray-500">잠시만 기다려 주세요.</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <TopBar />
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="bg-white border border-red-200 rounded-2xl p-8 max-w-md w-full text-center shadow-sm">
            <span className="text-3xl mb-2 inline-block">⚠️</span>
            <h2 className="text-lg font-bold text-gray-900 mb-2">의견서를 열 수 없습니다</h2>
            <p className="text-sm text-gray-600 mb-6 leading-relaxed">
              {error || '의견서가 아직 준비되지 않았거나 보관 기간이 만료되었습니다.'}
            </p>
            {review ? (
              <Link
                to={`/review/${review.review_id}`}
                className="inline-block bg-blue-600 text-white font-semibold text-xs px-5 py-2.5 rounded-xl hover:bg-blue-700 transition"
              >
                검토 대화 화면으로 돌아가기
              </Link>
            ) : (
              <Link
                to="/"
                className="inline-block bg-blue-600 text-white font-semibold text-xs px-5 py-2.5 rounded-xl hover:bg-blue-700 transition"
              >
                새로운 검토 시작하기
              </Link>
            )}
          </div>
        </div>
      </div>
    );
  }

  const gradeColors = {
    safe: {
      badge: 'bg-emerald-100 text-emerald-800 border-emerald-300',
      banner: 'from-emerald-500 to-teal-600',
      icon: '🟢',
      label: '안전',
    },
    caution: {
      badge: 'bg-amber-100 text-amber-900 border-amber-300',
      banner: 'from-amber-500 to-orange-600',
      icon: '🟡',
      label: '주의',
    },
    danger: {
      badge: 'bg-rose-100 text-rose-900 border-rose-300',
      banner: 'from-rose-600 to-red-700',
      icon: '🔴',
      label: '위험',
    },
  }[report.grade] || {
    badge: 'bg-gray-100 text-gray-800 border-gray-300',
    banner: 'from-gray-600 to-slate-700',
    icon: '⚪',
    label: '판정 중',
  };

  const rawRatio = report.debt_ratio || 0;
  const debtRatioVal = rawRatio <= 1.5 && rawRatio > 0 ? Math.round(rawRatio * 100) : Math.round(rawRatio);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <TopBar subject={review?.subject} counters={review?.counters} />

      {/* 토스트 알림 */}
      {copySuccess && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white text-xs font-semibold px-4 py-3 rounded-xl shadow-xl flex items-center gap-2 animate-bounce">
          <span>✅</span>
          <span>{copySuccess}</span>
        </div>
      )}

      <div className="max-w-4xl mx-auto w-full p-4 sm:p-6 lg:p-8 space-y-6">
        {/* 상단 네비게이션 & 액션 버튼 */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 pb-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Link to="/" className="hover:text-blue-600 transition">
              홈
            </Link>
            <span>/</span>
            <Link to={`/review/${report.review_id}`} className="hover:text-blue-600 transition">
              검토 대화
            </Link>
            <span>/</span>
            <span className="font-semibold text-gray-900">보증금 진단 의견서</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsOverrideOpen(true)}
              className="bg-white hover:bg-gray-50 text-gray-700 text-sm font-semibold px-3.5 py-2 rounded-xl border border-gray-200 shadow-sm transition flex items-center gap-1.5"
            >
              <span>✏️</span>
              <span>시세·금액 직접 수정</span>
            </button>
            <button
              onClick={handleCreateShare}
              disabled={isSharing}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold px-4 py-2 rounded-xl shadow-sm transition flex items-center gap-1.5"
            >
              <span>🔗</span>
              <span>{isSharing ? '생성 중...' : '의견서 공유하기'}</span>
            </button>
            <button
              onClick={() => window.print()}
              className="bg-white hover:bg-gray-50 text-gray-700 text-sm font-semibold px-3 py-2 rounded-xl border border-gray-200 shadow-sm transition"
              title="인쇄하기"
            >
              🖨️
            </button>
          </div>
        </div>

        {/* 1. 종합 등급 배너 */}
        <div className={`rounded-3xl bg-gradient-to-r ${gradeColors.banner} text-white p-6 sm:p-8 shadow-md`}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-1.5 bg-white/20 backdrop-blur-md text-white text-sm font-bold px-3 py-1 rounded-full border border-white/30">
                <span>{gradeColors.icon}</span>
                <span>LH 전세임대 권리분석 기준</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                보증금 위험도: <span className="underline decoration-white/50">{gradeColors.label}</span>
              </h1>
              <p className="text-sm sm:text-base text-white/90 leading-relaxed max-w-xl">
                {report.summary}
              </p>
            </div>

            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/20 text-center flex-shrink-0 min-w-[140px]">
              <span className="text-xs text-white/80 block mb-1">부채비율 (깡통전세 지수)</span>
              <span className="text-3xl font-black">{debtRatioVal > 0 ? `${debtRatioVal}%` : '산정 불가'}</span>
              <span className="text-[11px] text-white/70 block mt-1">
                {debtRatioVal > 90 ? '위험 (90% 초과)' : debtRatioVal > 70 ? '주의 (70~90%)' : '안전 (70% 이하)'}
              </span>
            </div>
          </div>

          {/* 판정 핵심 근거 목록 */}
          {report.reasons && report.reasons.length > 0 && (
            <div className="mt-6 pt-5 border-t border-white/20 space-y-1.5">
              <span className="text-sm font-bold text-white/90 block">📌 주요 판정 사유:</span>
              <ul className="space-y-1 text-sm text-white/85">
                {report.reasons.map((r, rIdx) => (
                  <li key={rIdx} className="flex items-start gap-1.5">
                    <span className="text-white/60">•</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* 2. 권리분석 & 부채비율 상세 카드 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <span>📊</span>
              <span>권리관계 및 보증금 보호 분석</span>
            </h2>
            <span className="text-xs text-gray-500">단위: 만원</span>
          </div>

          {/* 부채비율 게이지 바 */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-gray-700">시세 대비 총 부채 비율</span>
              <span className="font-extrabold text-blue-600">{debtRatioVal}%</span>
            </div>
            <div className="h-3 w-full bg-gray-100 rounded-full overflow-hidden flex">
              <div
                className={`h-full transition-all duration-500 ${
                  debtRatioVal > 90 ? 'bg-rose-500' : debtRatioVal > 70 ? 'bg-amber-500' : 'bg-emerald-500'
                }`}
                style={{ width: `${Math.min(debtRatioVal, 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-gray-500 px-0.5">
              <span>0%</span>
              <span className="text-emerald-600">70% (안전 기준선)</span>
              <span className="text-rose-600">90% (위험 기준선)</span>
              <span>100%+</span>
            </div>
          </div>

          {/* 권리 금액 세부 내역 그리드 */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
            <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-100">
              <span className="text-sm text-gray-600 block mb-1">추정 시세</span>
              <span className="text-sm sm:text-base font-bold text-gray-900">
                {report.price_manwon ? `${report.price_manwon.toLocaleString()}만원` : '시세 없음'}
              </span>
            </div>

            <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-100">
              <span className="text-sm text-gray-600 block mb-1">선순위 채권액(근저당)</span>
              <span className="text-sm sm:text-base font-bold text-gray-900">
                {(report.senior_debt_manwon || 0).toLocaleString()}만원
              </span>
            </div>

            <div className="bg-blue-50/60 rounded-xl p-3.5 border border-blue-100">
              <span className="text-xs text-blue-700 block mb-1">내 보증금</span>
              <span className="text-sm sm:text-base font-extrabold text-blue-900">
                {(report.deposit_manwon || review?.subject.deposit_manwon || 0).toLocaleString()}만원
              </span>
            </div>

            <div className="bg-emerald-50/60 rounded-xl p-3.5 border border-emerald-100">
              <span className="text-xs text-emerald-700 block mb-1">최우선변제 보호한도</span>
              <span className="text-sm sm:text-base font-bold text-emerald-900">
                {(report.priority_repayment_manwon || 0).toLocaleString()}만원
              </span>
            </div>
          </div>
        </div>

        {/* 3. 위험 신호(Risk Signals) */}
        {report.signals && report.signals.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <span>🚨</span>
              <span>확인된 위험 신호 ({report.signals.length}건)</span>
            </h2>

            <div className="space-y-2.5">
              {report.signals.map((sig, sIdx) => {
                const isDanger = sig.severity === 'danger';
                return (
                  <div
                    key={sIdx}
                    className={`rounded-xl p-4 border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                      isDanger
                        ? 'bg-rose-50/70 border-rose-200 text-rose-950'
                        : 'bg-amber-50/70 border-amber-200 text-amber-950'
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                            isDanger ? 'bg-rose-600 text-white' : 'bg-amber-600 text-white'
                          }`}
                        >
                          {isDanger ? '위험' : '주의'}
                        </span>
                        <span className="text-sm font-bold">{sig.label}</span>
                      </div>
                      {sig.description && (
                        <p className="text-sm text-gray-700 leading-relaxed">{sig.description}</p>
                      )}
                    </div>

                    {sig.source && (
                      <span className="text-[11px] text-gray-600 bg-white/80 border border-gray-200 rounded px-2 py-1 flex-shrink-0 self-start sm:self-center">
                        근거: {sig.source}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 4. 추천 특약사항 8종 (One-click 복사) */}
        {report.clauses && report.clauses.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                <span>📝</span>
                <span>계약서 필수 추천 특약사항</span>
              </h2>
              <span className="text-xs text-blue-600 font-semibold">공인중개사에게 작성을 요청하세요</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {report.clauses.map((clause, cIdx) => (
                <div
                  key={cIdx}
                  className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex flex-col justify-between gap-3 hover:border-blue-300 transition shadow-sm"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-gray-900">{clause.title}</span>
                    </div>
                    <p className="text-sm text-gray-800 bg-white border border-gray-200 rounded-lg p-3 font-mono leading-relaxed select-all">
                      "{clause.body || clause.text}"
                    </p>
                    {(clause.reason || clause.source) && (
                      <p className="text-sm text-gray-600 leading-relaxed">
                        💡 <strong>추천 이유:</strong> {clause.reason || clause.source}
                      </p>
                    )}
                  </div>

                  <button
                    onClick={() => handleCopyClause(clause.body || clause.text || '', clause.title)}
                    className="w-full bg-white hover:bg-blue-50 text-blue-600 hover:text-blue-700 text-sm font-bold py-2 rounded-lg border border-blue-200 transition flex items-center justify-center gap-1"
                  >
                    <span>📋</span>
                    <span>특약 문구 복사</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 5. 단계별 안전 체크리스트 */}
        {report.todos && report.todos.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <span>✅</span>
              <span>단계별 보증금 보호 체크리스트</span>
            </h2>

            <div className="space-y-3">
              {report.todos.map((todo, tIdx) => {
                const todoKey = `todo_${tIdx}`;
                const isChecked = !!checkedTodos[todoKey];
                const phaseLabel = {
                  before_contract: '계약 체결 전',
                  closing: '잔금 지급 시',
                  move_in: '입주 및 전입 후',
                }[todo.phase] || '확인 사항';

                return (
                  <div
                    key={tIdx}
                    onClick={() => toggleTodo(todoKey)}
                    className={`rounded-xl p-4 border transition cursor-pointer flex items-start gap-3.5 ${
                      isChecked
                        ? 'bg-gray-50 border-gray-200 text-gray-500 line-through'
                        : 'bg-white border-gray-200 hover:border-blue-300 text-gray-900 shadow-sm'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleTodo(todoKey)}
                      className="mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-bold bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                          {phaseLabel}
                        </span>
                        <span className="text-sm font-bold">{todo.title}</span>
                      </div>
                      <p className="text-sm text-gray-600 leading-relaxed">{todo.text}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 하단 법적 고지 및 공유 바 */}
        <div className="bg-slate-100 rounded-2xl p-5 text-center text-xs text-slate-600 space-y-2">
          <p>보증금지킴의 권리분석 의견서는 국토교통부·LH·HUG 기준을 기반으로 산출된 참고용 데이터입니다.</p>
          <div className="flex justify-center gap-4 pt-2">
            <Link to={`/review/${report.review_id}`} className="text-blue-600 hover:underline font-semibold">
              ← 검토 대화 타래 다시 보기
            </Link>
            <span>|</span>
            <Link to="/criteria" className="text-blue-600 hover:underline font-semibold">
              전체 판정 기준표 보기
            </Link>
          </div>
        </div>
      </div>

      {/* 시세/금액 직접 수정 모달 */}
      {isOverrideOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-2xl space-y-5 animate-scaleUp">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-gray-900">시세 및 권리금액 직접 수정</h3>
              <button
                onClick={() => setIsOverrideOpen(false)}
                className="text-gray-500 hover:text-gray-600 text-lg"
              >
                ✕
              </button>
            </div>

            <p className="text-sm text-gray-600 leading-relaxed">
              공인중개사나 인근 실거래가를 통해 확인한 정확한 시세가 있다면 직접 입력해 재판정할 수 있습니다.
            </p>

            <form onSubmit={handleOverrideSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-gray-700">추정 시세 (만원)</label>
                <input
                  type="number"
                  value={overridePrice}
                  onChange={(e) => setOverridePrice(e.target.value)}
                  placeholder="예: 25000 (2억 5천만원)"
                  className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-xs text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsOverrideOpen(false)}
                  className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-semibold py-2.5 rounded-xl transition"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={isOverriding}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white text-sm font-bold py-2.5 rounded-xl transition shadow"
                >
                  {isOverriding ? '재판정 중...' : '재판정하기'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 공유 링크 안내 모달 */}
      {shareUrl && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-2xl space-y-5 animate-scaleUp">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-gray-900">🔗 의견서 공유 링크</h3>
              <button
                onClick={() => setShareUrl(null)}
                className="text-gray-500 hover:text-gray-600 text-lg"
              >
                ✕
              </button>
            </div>

            <p className="text-sm text-gray-600 leading-relaxed">
              임대인 이름과 상세 주소가 안전하게 마스킹된 읽기 전용 진단서 링크입니다. 가족이나 부동산 중개사에게 전달해 보세요.
            </p>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between gap-2">
              <span className="text-xs text-slate-800 truncate font-mono">{shareUrl}</span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(shareUrl);
                  setCopySuccess('링크가 복사되었습니다!');
                  setTimeout(() => setCopySuccess(null), 3000);
                }}
                className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold px-3 py-1.5 rounded-lg flex-shrink-0 transition"
              >
                복사
              </button>
            </div>

            <p className="text-xs text-gray-500 text-center">
              ⏳ 발급일로부터 7일간 열람할 수 있습니다.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
