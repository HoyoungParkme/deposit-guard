import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { TopBar } from '../components/TopBar';
import { DocumentPanel } from '../components/DocumentPanel';
import { ReviewView, getReview, ApiError } from '../api/client';

export const ReviewPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [review, setReview] = useState<ReviewView | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [highlightBlockId] = useState<string | null>(null);
  const [highlightCitationLabel] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let isMounted = true;
    setIsLoading(true);
    setError(null);

    getReview(id)
      .then((data) => {
        if (isMounted) {
          setReview(data);
          if (data.documents && data.documents.length > 0) {
            setSelectedDocId(data.documents[0].document_id);
          }
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          if (err instanceof ApiError) {
            setError(err.detail);
          } else {
            setError('검토 정보를 불러오는 데 실패했습니다.');
          }
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [id]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <span className="text-3xl animate-spin">⏳</span>
          <p className="text-sm font-semibold text-gray-700">등기부 검토 정보를 불러오는 중...</p>
          <p className="text-xs text-gray-400">잠시만 기다려 주세요.</p>
        </div>
      </div>
    );
  }

  if (error || !review) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <TopBar />
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="bg-white border border-red-200 rounded-2xl p-8 max-w-md w-full text-center shadow-sm">
            <span className="text-3xl mb-2 inline-block">⚠️</span>
            <h2 className="text-lg font-bold text-gray-900 mb-2">검토를 열 수 없습니다</h2>
            <p className="text-xs text-gray-600 mb-6 leading-relaxed">
              {error || '검토가 존재하지 않거나 보관 기간(24시간)이 만료되었습니다.'}
            </p>
            <Link
              to="/"
              className="inline-block bg-blue-600 text-white font-semibold text-xs px-5 py-2.5 rounded-xl hover:bg-blue-700 transition"
            >
              새로운 검토 시작하기
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50 overflow-hidden">
      {/* 고정 상단 바 */}
      <TopBar subject={review.subject} counters={review.counters} />

      {/* 2열 레이아웃: 대화 타래 + 문서 패널 */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden" data-el="ui-2-review">
        {/* 좌측 대화 영역 (thread-col) */}
        <div className="flex-1 flex flex-col bg-white border-r border-gray-200 overflow-y-auto p-4 sm:p-6">
          <div className="thread space-y-4 max-w-2xl mx-auto w-full" data-el="2">
            {/* 에이전트 첫 말풍선 */}
            <div className="msg-agent flex gap-3 items-start" data-el="2a">
              <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold flex-shrink-0 shadow-sm">
                지킴
              </div>
              <div className="flex-1 bg-gray-50 border border-gray-200 rounded-2xl rounded-tl-none p-4 text-sm text-gray-800 leading-relaxed shadow-sm">
                <p className="font-semibold text-gray-900 mb-1">
                  등기부 파싱 및 기본 권리정보 추출이 완료되었습니다.
                </p>
                <p className="text-xs text-gray-600 mb-3">
                  오른쪽 문서 패널에서 표제부·갑구·을구 원문 표를 바로 확인하실 수 있습니다.
                </p>

                {/* 대상 물건 요약 카드 */}
                <div className="bg-white rounded-xl border border-gray-200 p-3 text-xs space-y-1.5 mb-2">
                  <div className="flex justify-between">
                    <span className="text-gray-500">소재지/지역</span>
                    <span className="font-medium text-gray-900">{review.subject.region || '등기부 표제부 참조'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">계약 형태 및 보증금</span>
                    <span className="font-bold text-blue-600">
                      {review.subject.contract_type === 'jeonse' ? '전세' : '월세'}{' '}
                      {review.subject.deposit_manwon.toLocaleString()}만원
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">등록된 문서</span>
                    <span className="text-gray-800 font-medium">
                      {review.documents.map((d) => d.label).join(', ')} ({review.documents.length}건)
                    </span>
                  </div>
                </div>

                <div className="text-[11px] text-gray-500 bg-blue-50 border border-blue-100 rounded-lg p-2.5">
                  💡 <strong>안내:</strong> 슬라이스 B1에서는 등기부 파싱과 원문 패널 조회가 연동되었습니다.
                  다음 단계(B2)에서 에이전트 자율 권리분석 루프(도구 호출, 질문, 판정)가 연결됩니다.
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 우측 문서 패널 (doc-panel) */}
        <div className="w-full lg:w-[460px] xl:w-[520px] flex-shrink-0 h-[450px] lg:h-full flex flex-col bg-white">
          <DocumentPanel
            reviewId={review.review_id}
            documents={review.documents}
            selectedDocId={selectedDocId}
            onSelectDoc={(docId) => setSelectedDocId(docId)}
            highlightBlockId={highlightBlockId}
            highlightCitationLabel={highlightCitationLabel}
          />
        </div>
      </div>
    </div>
  );
};
