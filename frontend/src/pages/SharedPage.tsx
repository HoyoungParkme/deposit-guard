import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { TopBar } from '../components/TopBar';
import { SharedView, getSharedView, ApiError } from '../api/client';

export const SharedPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();

  const [shared, setShared] = useState<SharedView | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    setIsLoading(true);
    setError(null);

    getSharedView(token)
      .then((data) => {
        setShared(data);
      })
      .catch((err) => {
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError('공유된 의견서를 불러올 수 없습니다.');
        }
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [token]);

  const handleCopyClause = async (clauseText: string, title: string) => {
    try {
      await navigator.clipboard.writeText(clauseText);
      setCopySuccess(`"${title}" 특약 문구가 복사되었습니다.`);
      setTimeout(() => setCopySuccess(null), 3000);
    } catch {
      alert('복사에 실패했습니다.');
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <span className="text-3xl animate-spin">⏳</span>
          <p className="text-sm font-semibold text-gray-700">공유된 보증금 진단서를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (error || !shared) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col">
        <TopBar />
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="bg-white border border-red-200 rounded-3xl p-8 max-w-md w-full text-center shadow-sm space-y-4">
            <span className="text-4xl inline-block">⚠️</span>
            <h2 className="text-lg font-bold text-gray-900">공유 링크가 만료되었거나 존재하지 않습니다</h2>
            <p className="text-xs text-gray-600 leading-relaxed">
              {error || '보증금지킴 공유 링크는 발급 후 7일간만 열람이 가능합니다.'}
            </p>
            <Link
              to="/"
              className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs px-5 py-3 rounded-xl transition shadow"
            >
              내 보증금 직접 진단해보기
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const report = shared.report;
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
    label: '판정',
  };

  const rawRatio = report.debt_ratio || 0;
  const debtRatioVal = rawRatio <= 1.5 && rawRatio > 0 ? Math.round(rawRatio * 100) : Math.round(rawRatio);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <TopBar />

      {copySuccess && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white text-xs font-semibold px-4 py-3 rounded-xl shadow-xl flex items-center gap-2 animate-bounce">
          <span>✅</span>
          <span>{copySuccess}</span>
        </div>
      )}

      <div className="max-w-4xl mx-auto w-full p-4 sm:p-6 lg:p-8 space-y-6">
        {/* 상단 보안 알림 배너 */}
        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2 text-xs text-blue-900">
            <span className="text-base">🔒</span>
            <span className="font-semibold">
              임대인 이름과 상세 주소가 안전하게 마스킹된 읽기 전용 공유 진단서입니다.
            </span>
          </div>
          <Link
            to="/"
            className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-4 py-2 rounded-xl shadow transition self-start sm:self-auto flex-shrink-0"
          >
            내 집도 검토해보기 →
          </Link>
        </div>

        {/* 1. 종합 등급 배너 */}
        <div className={`rounded-3xl bg-gradient-to-r ${gradeColors.banner} text-white p-6 sm:p-8 shadow-md`}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-1.5 bg-white/20 backdrop-blur-md text-white text-xs font-bold px-3 py-1 rounded-full border border-white/30">
                <span>{gradeColors.icon}</span>
                <span>LH 전세임대 권리분석 기준</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                보증금 위험도: {gradeColors.label}
              </h1>
              <p className="text-xs sm:text-sm text-white/90 leading-relaxed max-w-xl">
                {report.summary}
              </p>
            </div>

            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/20 text-center flex-shrink-0 min-w-[140px]">
              <span className="text-[11px] text-white/80 block mb-1">부채비율</span>
              <span className="text-3xl font-black">{debtRatioVal > 0 ? `${debtRatioVal}%` : '-'}</span>
              <span className="text-[10px] text-white/70 block mt-1">
                {debtRatioVal > 90 ? '위험 (90% 초과)' : debtRatioVal > 70 ? '주의 (70~90%)' : '안전 (70% 이하)'}
              </span>
            </div>
          </div>

          {report.reasons && report.reasons.length > 0 && (
            <div className="mt-6 pt-5 border-t border-white/20 space-y-1.5">
              <span className="text-xs font-bold text-white/90 block">📌 판정 사유:</span>
              <ul className="space-y-1 text-xs text-white/85">
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

        {/* 2. 권리분석 요약 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-4">
          <h2 className="text-sm font-bold text-gray-900 flex items-center gap-2">
            <span>📊</span>
            <span>권리금액 요약</span>
          </h2>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-100">
              <span className="text-[11px] text-gray-500 block mb-1">추정 시세</span>
              <span className="text-sm font-bold text-gray-900">
                {report.price_manwon ? `${report.price_manwon.toLocaleString()}만원` : '시세 미정'}
              </span>
            </div>

            <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-100">
              <span className="text-[11px] text-gray-500 block mb-1">선순위 채권액</span>
              <span className="text-sm font-bold text-gray-900">
                {(report.senior_debt_manwon || 0).toLocaleString()}만원
              </span>
            </div>

            <div className="bg-blue-50/60 rounded-xl p-3.5 border border-blue-100">
              <span className="text-[11px] text-blue-700 block mb-1">보증금</span>
              <span className="text-sm font-extrabold text-blue-900">
                {(report.deposit_manwon || 0).toLocaleString()}만원
              </span>
            </div>

            <div className="bg-emerald-50/60 rounded-xl p-3.5 border border-emerald-100">
              <span className="text-[11px] text-emerald-700 block mb-1">최우선변제 한도</span>
              <span className="text-sm font-bold text-emerald-900">
                {(report.priority_repayment_manwon || 0).toLocaleString()}만원
              </span>
            </div>
          </div>
        </div>

        {/* 3. 추천 특약사항 */}
        {report.clauses && report.clauses.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-4">
            <h2 className="text-sm font-bold text-gray-900 flex items-center gap-2">
              <span>📝</span>
              <span>계약서 필수 추천 특약사항</span>
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {report.clauses.map((clause, cIdx) => (
                <div
                  key={cIdx}
                  className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex flex-col justify-between gap-3 shadow-xs"
                >
                  <div className="space-y-1.5">
                    <span className="text-xs font-bold text-gray-900">{clause.title}</span>
                    <p className="text-xs text-gray-800 bg-white border border-gray-200 rounded-lg p-3 font-mono leading-relaxed select-all">
                      "{clause.body || clause.text}"
                    </p>
                  </div>
                  <button
                    onClick={() => handleCopyClause(clause.body || clause.text || '', clause.title)}
                    className="w-full bg-white hover:bg-blue-50 text-blue-600 text-xs font-bold py-2 rounded-lg border border-blue-200 transition flex items-center justify-center gap-1"
                  >
                    <span>📋</span>
                    <span>특약 복사</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 하단 CTA */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-3xl p-8 text-center text-white space-y-3 shadow-lg">
          <h3 className="text-lg sm:text-xl font-bold">내가 계약할 집도 안전한지 확인해보세요!</h3>
          <p className="text-xs text-white/80 max-w-md mx-auto">
            등기부등본만 올리면 1분 만에 깡통전세 여부와 필수 특약사항을 무료로 진단해 드립니다. (로그인 불필요)
          </p>
          <div className="pt-2">
            <Link
              to="/"
              className="inline-block bg-white hover:bg-gray-100 text-blue-700 font-extrabold text-xs px-6 py-3 rounded-xl shadow-md transition"
            >
              보증금 무료 진단 시작하기 →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
