import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { TopBar } from '../components/TopBar';
import { Composer } from '../components/Composer';
import { SampleCase, getSamples, createReview, CreateReviewParams, ApiError } from '../api/client';

export const StartPage: React.FC = () => {
  const navigate = useNavigate();
  const [samples, setSamples] = useState<SampleCase[]>([]);
  const [selectedSample, setSelectedSample] = useState<SampleCase | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    getSamples()
      .then((data) => {
        setSamples(data);
      })
      .catch((err) => {
        console.error('Failed to load samples:', err);
      });
  }, []);

  const handleSelectSample = (sample: SampleCase) => {
    if (selectedSample?.sample_id === sample.sample_id) {
      setSelectedSample(null);
    } else {
      setSelectedSample(sample);
      setErrorMessage(null);
    }
  };

  const handleSubmit = async (params: CreateReviewParams) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await createReview(params);
      navigate(`/review/${res.review_id}`);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMessage(err.detail);
      } else {
        setErrorMessage('검토 요청 중 오류가 발생했습니다. 다시 시도해 주세요.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <TopBar />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-10 flex flex-col">
        {/* 키커, 타이틀, 설명 */}
        <div className="text-center mb-8">
          <div className="flex flex-wrap items-center justify-center gap-2 mb-3">
            <div
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100 text-blue-800 text-xs font-semibold"
              data-el="2b"
            >
              <span>🛡️</span>
              <span>LH 전세임대 권리분석 기준 그대로</span>
            </div>
            <Link
              to="/guide"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold border border-indigo-200/80 transition shadow-2xs"
            >
              <span>📸</span>
              <span>1분 시각 이용 가이드 보기 →</span>
            </Link>
          </div>
          <h1
            className="text-3xl sm:text-4xl font-extrabold text-gray-950 tracking-tight mb-3"
            data-el="2"
          >
            이 집, 계약해도 될까요?
          </h1>
          <p className="text-sm sm:text-base text-gray-600" data-el="2c">
            확인할 것을 스스로 정해 검토하고 의견서를 냅니다.
          </p>
        </div>

        {/* 입력 상자 (드롭존 + 입력 필드) */}
        <div className="w-full mb-8">
          <Composer
            selectedSample={selectedSample}
            onClearSample={() => setSelectedSample(null)}
            onSubmit={handleSubmit}
            isLoading={isLoading}
            errorMessage={errorMessage}
          />
        </div>

        {/* 예시 등기부 카드 3개 */}
        <div className="mb-10" data-el="4">
          <div className="flex items-center justify-between mb-3 px-1">
            <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400">
              등기부 파일이 없다면? 실제 사례로 체험하기
            </h2>
            <span className="text-[11px] text-gray-400">실제 등기부 파싱 및 분석</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
            {samples.map((sample) => {
              const isSelected = selectedSample?.sample_id === sample.sample_id;
              return (
                <div
                  key={sample.sample_id}
                  onClick={() => handleSelectSample(sample)}
                  className={`p-4 rounded-xl border-2 transition cursor-pointer flex flex-col justify-between ${
                    isSelected
                      ? 'border-blue-600 bg-blue-50/60 ring-2 ring-blue-500/20 shadow-sm'
                      : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between gap-1 mb-2">
                      <span className="text-xl">
                        {sample.title.includes('아파트') ? '🏢' : sample.title.includes('빌라') ? '🏡' : '🏘️'}
                      </span>
                      {isSelected ? (
                        <span className="text-[11px] font-bold text-blue-600 bg-blue-100 px-2 py-0.5 rounded-full">
                          선택됨
                        </span>
                      ) : (
                        <span className="text-[11px] text-gray-400 font-medium">선택하기</span>
                      )}
                    </div>
                    <h3 className="font-bold text-gray-900 text-sm mb-1">{sample.title}</h3>
                    <p className="text-xs text-gray-500 leading-snug line-clamp-2">
                      {sample.summary}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
                    <span className="text-gray-500">{sample.region}</span>
                    <span className="font-semibold text-gray-800">
                      {sample.contract_type === 'jeonse' ? '전세' : '월세'}{' '}
                      {(sample.deposit_manwon / 10000).toFixed(sample.deposit_manwon % 10000 === 0 ? 0 : 1)}억
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 서비스 작동 원리 및 가이드 (어떤 문제를 어떻게 해결하나요?) */}
        <div className="mb-12 bg-white border border-gray-200/90 rounded-2xl p-6 sm:p-8 shadow-xs">
          <div className="text-center max-w-xl mx-auto mb-8">
            <span className="text-xs font-bold text-blue-600 bg-blue-50 border border-blue-200/60 px-3 py-1 rounded-full">
              서비스 안내 & 권리분석 가이드
            </span>
            <h2 className="text-xl font-bold text-gray-900 mt-2">
              등기부등본 1장이면 전세 계약 전 안전을 지킬 수 있습니다
            </h2>
            <p className="text-xs text-gray-500 mt-1.5">
              어려운 부동산 등기 용어와 복잡한 계산을 AI 권리분석 에이전트가 1분 만에 진단합니다.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
            <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-4.5 space-y-2">
              <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
                1
              </div>
              <h3 className="font-bold text-gray-900 text-sm">어떤 파일을 넣나요?</h3>
              <p className="text-xs text-gray-600 leading-relaxed">
                인터넷등기소나 공인중개사에게 받은 <strong>등기사항전부증명서(PDF·사진)</strong>를 첨부하세요. 파일이 없다면 아래 예시 카드로 바로 체험할 수 있습니다.
              </p>
            </div>

            <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-4.5 space-y-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-sm">
                2
              </div>
              <h3 className="font-bold text-gray-900 text-sm">어떤 기준으로 분석하나요?</h3>
              <p className="text-xs text-gray-600 leading-relaxed">
                <strong>LH 전세임대 권리분석 기준</strong>(부채비율 70% 안전선), <strong>국토부 실거래가</strong>, <strong>HUG 악성 임대인 명단</strong>, 11대 전세사기 위험 신호를 교차 검증합니다.
              </p>
            </div>

            <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-4.5 space-y-2">
              <div className="w-8 h-8 rounded-lg bg-emerald-600 text-white flex items-center justify-center font-bold text-sm">
                3
              </div>
              <h3 className="font-bold text-gray-900 text-sm">어떤 결과를 받나요?</h3>
              <p className="text-xs text-gray-600 leading-relaxed">
                종합 안전도 등급, 깡통전세 지수, 그리고 계약서에 바로 넣을 수 있는 <strong>법무부 표준 맞춤 특약 6종(원클릭 복사)</strong>과 <strong>13대 체크리스트</strong>를 제공합니다.
              </p>
            </div>
          </div>

          <div className="bg-blue-50/60 border border-blue-100 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-blue-950">
            <div className="flex items-center gap-2.5">
              <span className="text-lg">📖</span>
              <span>서비스가 어떻게 작동하고 분석하는지 실제 화면으로 확인해보세요.</span>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <Link
                to="/guide"
                className="font-bold text-indigo-700 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 px-3.5 py-1.5 rounded-lg shadow-2xs transition"
              >
                📸 화면별 가이드 보기 →
              </Link>
              <Link
                to="/criteria"
                className="font-bold text-blue-600 hover:text-blue-700 bg-white border border-blue-200 px-3.5 py-1.5 rounded-lg shadow-2xs transition"
              >
                ⚖️ 판정 기준표 →
              </Link>
            </div>
          </div>
        </div>

        {/* 미저장 고지 */}
        <div
          className="bg-slate-100/80 border border-slate-200/80 rounded-2xl p-4.5 text-xs text-slate-600 space-y-1"
          data-el="5"
        >
          <p className="font-bold text-slate-800 flex items-center gap-1.5">
            <span>🔒</span>
            <span>개인정보 보호 및 자동 파기 원칙</span>
          </p>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            올려주신 등기부는 분석 목적으로만 일시 사용되며, 24시간 후 자동 영구 파기됩니다.
            서버에 보관되거나 AI 모델 학습에 사용되지 않습니다.
          </p>
        </div>
      </main>

      {/* 푸터 */}
      <footer
        className="w-full border-t border-gray-200 bg-white py-6 px-4 text-center text-xs text-gray-400"
        data-el="6"
      >
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>
            보증금지킴은 법률 상담이나 공인중개사를 대체하지 않는 참고용 권리분석 의견서입니다.
          </p>
          <p className="text-[11px]">
            기준 출처: 국토교통부 · LH 한국토지주택공사 · HUG 주택도시보증공사 · 대법원 인터넷등기소
          </p>
        </div>
      </footer>
    </div>
  );
};
