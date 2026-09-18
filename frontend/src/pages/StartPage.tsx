import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
          <div
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100 text-blue-800 text-xs font-semibold mb-3"
            data-el="2b"
          >
            <span>🛡️</span>
            <span>LH 전세임대 권리분석 기준 그대로</span>
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

        {/* 미저장 고지 */}
        <div
          className="p-4 bg-gray-100/70 border border-gray-200 rounded-xl text-center text-xs text-gray-500 mb-8"
          data-el="5"
        >
          <p className="font-medium text-gray-700 mb-0.5">🔒 개인정보 보호 및 자동 파기 원칙</p>
          <p>
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
