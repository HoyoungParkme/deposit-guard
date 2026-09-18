import React, { useEffect, useState, useRef } from 'react';
import { ReviewDocumentItem, getDocumentHtml } from '../api/client';

interface DocumentPanelProps {
  reviewId: string;
  documents: ReviewDocumentItem[];
  selectedDocId?: string | null;
  onSelectDoc?: (docId: string) => void;
  highlightBlockId?: string | null;
  highlightCitationLabel?: string | null;
  onClose?: () => void;
}

export const DocumentPanel: React.FC<DocumentPanelProps> = ({
  reviewId,
  documents,
  selectedDocId,
  onSelectDoc,
  highlightBlockId,
  highlightCitationLabel,
  onClose,
}) => {
  const [activeDocId, setActiveDocId] = useState<string | null>(
    selectedDocId || (documents.length > 0 ? documents[0].document_id : null)
  );
  const [htmlContent, setHtmlContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const sheetRef = useRef<HTMLDivElement>(null);

  // 선택된 문서 ID가 prop으로 넘어오면 동기화
  useEffect(() => {
    if (selectedDocId) {
      setActiveDocId(selectedDocId);
    } else if (documents.length > 0 && !activeDocId) {
      setActiveDocId(documents[0].document_id);
    }
  }, [selectedDocId, documents]);

  // activeDocId 변경 시 원문 HTML 로드
  useEffect(() => {
    if (!reviewId || !activeDocId) return;

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    getDocumentHtml(reviewId, activeDocId)
      .then((html) => {
        if (isMounted) {
          setHtmlContent(html);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || '등기부 원문을 불러오지 못했습니다.');
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [reviewId, activeDocId]);

  // highlightBlockId 변경 시 또는 HTML 렌더 후 스크롤 및 하이라이트 클래스 적용
  useEffect(() => {
    if (!sheetRef.current || !htmlContent) return;

    // 기존 하이라이트 제거
    const prevHighlighted = sheetRef.current.querySelectorAll('.is-highlighted');
    prevHighlighted.forEach((el) => el.classList.remove('is-highlighted'));

    if (highlightBlockId) {
      const target = sheetRef.current.querySelector(`[data-block-id="${highlightBlockId}"]`);
      if (target) {
        target.classList.add('is-highlighted');
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [highlightBlockId, htmlContent]);

  const handleTabClick = (docId: string) => {
    setActiveDocId(docId);
    if (onSelectDoc) {
      onSelectDoc(docId);
    }
  };

  const getDocBadgeLabel = (kind: string) => {
    switch (kind) {
      case 'building':
        return '건물';
      case 'land':
        return '토지';
      case 'collective':
        return '집합건물';
      default:
        return '등기부';
    }
  };

  return (
    <aside
      className="doc-panel flex flex-col h-full bg-white border-l border-gray-200 w-full"
      data-el="7"
    >
      {/* 탭 헤더 */}
      <div className="tabs flex items-center border-b border-gray-200 bg-gray-50 px-2 pt-2 gap-1 overflow-x-auto">
        {documents.map((doc) => {
          const isActive = doc.document_id === activeDocId;
          return (
            <button
              key={doc.document_id}
              onClick={() => handleTabClick(doc.document_id)}
              className={`px-3 py-2 text-xs font-medium rounded-t-lg transition flex items-center gap-1.5 whitespace-nowrap ${
                isActive
                  ? 'bg-white text-blue-700 border-t-2 border-t-blue-600 border-x border-gray-200 -mb-[1px] shadow-sm font-semibold'
                  : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
              }`}
            >
              <span
                className={`text-[10px] px-1 py-0.2 rounded font-bold ${
                  doc.kind === 'land'
                    ? 'bg-amber-100 text-amber-800'
                    : 'bg-blue-100 text-blue-800'
                }`}
              >
                {getDocBadgeLabel(doc.kind)}
              </span>
              <span>{doc.label || '등기부'}</span>
            </button>
          );
        })}
      </div>

      {/* 패널 머리: 인용 위치 안내 및 닫기 버튼 */}
      <div className="panel-head px-4 py-2 border-b border-gray-100 bg-gray-50/50 flex items-center justify-between text-xs text-gray-600">
        <div className="flex items-center gap-2 truncate">
          <span className="font-semibold text-gray-800">등기부 원문 표</span>
          {highlightCitationLabel && (
            <span className="bg-amber-100 text-amber-900 border border-amber-300 px-2 py-0.5 rounded text-[11px] font-medium">
              인용: {highlightCitationLabel}
            </span>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1 rounded hover:bg-gray-100"
            title="패널 닫기"
          >
            ✕
          </button>
        )}
      </div>

      {/* 원문 영역 (sheet) */}
      <div className="flex-1 overflow-y-auto p-4" ref={sheetRef}>
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-48 text-gray-400 gap-2">
            <span className="text-xl animate-spin">⏳</span>
            <p className="text-xs">등기부 원문을 불러오는 중...</p>
          </div>
        ) : error ? (
          <div className="p-4 bg-red-50 text-red-700 rounded-lg text-xs">
            <p className="font-semibold">오류 발생</p>
            <p>{error}</p>
          </div>
        ) : htmlContent ? (
          <div
            className="doc-sheet text-gray-800 leading-relaxed"
            dangerouslySetInnerHTML={{ __html: htmlContent }}
          />
        ) : (
          <div className="text-xs text-gray-400 text-center py-12">
            표시할 등기부 원문이 없습니다.
          </div>
        )}
      </div>

      {/* 하단: 이 줄이 쓰인 곳 (usages) */}
      <div className="usages border-t border-gray-200 bg-gray-50 p-3 text-xs text-gray-500">
        {highlightBlockId ? (
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
            <span className="font-medium text-gray-700">이 줄이 쓰인 곳:</span>
            <span>{highlightCitationLabel || highlightBlockId} (에이전트 판단 근거)</span>
          </div>
        ) : (
          <div className="text-gray-400">
            대화 말풍선 속 인용 칩을 누르면 해당 등기부 줄로 바로 이동합니다.
          </div>
        )}
      </div>
    </aside>
  );
};
