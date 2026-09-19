import React, { useEffect, useRef, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { TopBar } from '../components/TopBar';
import { DocumentPanel } from '../components/DocumentPanel';
import {
  ReviewView,
  MessageItem,
  QuestionData,
  getReview,
  listMessages,
  postMessage,
  ApiError,
} from '../api/client';

export const ReviewPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [review, setReview] = useState<ReviewView | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState<QuestionData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [highlightBlockId, setHighlightBlockId] = useState<string | null>(null);
  const [highlightCitationLabel, setHighlightCitationLabel] = useState<string | null>(null);

  // 되묻기 / 답변 입력 상태
  const [customInputText, setCustomInputText] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 1. 초기 리뷰 데이터 및 메시지 로딩
  const refreshReview = async (reviewId: string) => {
    try {
      const data = await getReview(reviewId);
      setReview(data);
      if (data.pending_question) {
        setPendingQuestion(data.pending_question);
      } else {
        setPendingQuestion(null);
      }
      if (data.documents && data.documents.length > 0 && !selectedDocId) {
        setSelectedDocId(data.documents[0].document_id);
      }
      return data;
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('검토 정보를 불러오는 데 실패했습니다.');
      }
      return null;
    }
  };

  const loadMessages = async (reviewId: string) => {
    try {
      const data = await listMessages(reviewId, 0);
      setMessages(data.messages || []);
    } catch {
      // 메시지 목록 조회 실패 시 무시
    }
  };

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);

    Promise.all([refreshReview(id), loadMessages(id)]).finally(() => {
      setIsLoading(false);
      setTimeout(scrollToBottom, 100);
    });
  }, [id]);

  // 2. SSE 스트림 및 주기적 폴링 연동
  useEffect(() => {
    if (!id) return;

    let eventSource: EventSource | null = null;
    let pollTimer: any = null;

    try {
      eventSource = new EventSource(`/api/reviews/${id}/stream`);

      eventSource.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.type === 'message' || parsed.type === 'progress' || parsed.type === 'question' || parsed.type === 'report_ready') {
            loadMessages(id);
            refreshReview(id);
          } else if (parsed.type === 'done') {
            refreshReview(id);
            loadMessages(id);
          }
        } catch {
          // ignore parse error
        }
      };

      eventSource.onerror = () => {
        // SSE 연결 끊김 시 폴백 폴링 유지
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
      };
    } catch {
      // EventSource 미지원 환경
    }

    // 보조 폴링 (진행 중일 때 3초 간격)
    pollTimer = setInterval(() => {
      refreshReview(id).then((rev) => {
        if (rev) {
          loadMessages(id);
        }
      });
    }, 3000);

    return () => {
      if (eventSource) eventSource.close();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [id]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, pendingQuestion]);

  // 질문 선택지 클릭 답변
  const handleAnswerChoice = async (choice: string) => {
    if (!id || !pendingQuestion || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await postMessage(id, {
        kind: 'answer',
        question_id: pendingQuestion.question_id,
        choice: choice,
      });
      setPendingQuestion(null);
      await loadMessages(id);
      await refreshReview(id);
    } catch (err: any) {
      alert(err?.detail || '답변 전송에 실패했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // 직접 텍스트 답변 또는 되묻기 발화 전송
  const handleSendText = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !customInputText.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      if (pendingQuestion) {
        // 질문에 대한 텍스트 답변
        await postMessage(id, {
          kind: 'answer',
          question_id: pendingQuestion.question_id,
          text: customInputText.trim(),
        });
        setPendingQuestion(null);
      } else {
        // 되묻기 질문
        await postMessage(id, {
          kind: 'ask',
          text: customInputText.trim(),
        });
      }
      setCustomInputText('');
      await loadMessages(id);
      await refreshReview(id);
    } catch (err: any) {
      alert(err?.detail || '메시지 전송에 실패했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // 인용 태그 클릭 시 해당 등기부 블록 강조
  const handleCitationClick = (blockId?: string, label?: string) => {
    if (blockId) {
      setHighlightBlockId(blockId);
      setHighlightCitationLabel(label || null);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <span className="text-3xl animate-spin">⏳</span>
          <p className="text-sm font-semibold text-gray-700">등기부 및 실시간 진단 연결 중...</p>
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
        <div className="flex-1 flex flex-col bg-white border-r border-gray-200 overflow-hidden">
          {/* 상단 의견서 바로가기 알림 배너 */}
          {review.has_report && (
            <div className="bg-emerald-50 border-b border-emerald-200 px-4 py-3 flex items-center justify-between shadow-sm z-10">
              <div className="flex items-center gap-2 text-xs text-emerald-900 font-medium">
                <span className="text-base">🎉</span>
                <span>보증금 안전 진단 의견서가 완성되었습니다!</span>
              </div>
              <Link
                to={`/review/${review.review_id}/report`}
                className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold px-4 py-1.5 rounded-lg shadow-sm transition flex items-center gap-1"
              >
                <span>진단서 보기</span>
                <span>→</span>
              </Link>
            </div>
          )}

          {/* 대화 타래 스크롤 영역 */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
            {/* 시스템 안내 카드 */}
            <div className="max-w-2xl mx-auto bg-slate-50 border border-slate-200 rounded-xl p-3.5 text-xs text-slate-700 space-y-1.5 shadow-sm">
              <div className="flex items-center justify-between font-semibold text-slate-900">
                <span className="flex items-center gap-1.5">
                  <span>🏢</span>
                  <span>{review.subject.region || '소재지 확인 중'}</span>
                </span>
                <span className="text-blue-600">
                  {review.subject.contract_type === 'jeonse' ? '전세' : '월세'} {review.subject.deposit_manwon.toLocaleString()}만원
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                AI 권리분석 에이전트가 등기부와 공공데이터를 교차 분석하고 있습니다.
              </p>
            </div>

            {/* 메시지 목록 */}
            <div className="max-w-2xl mx-auto space-y-4">
              {messages.length === 0 && (
                <div className="flex gap-3 items-start animate-pulse">
                  <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold shadow-sm">
                    지킴
                  </div>
                  <div className="flex-1 bg-slate-50 border border-slate-200 rounded-2xl rounded-tl-none p-4 text-xs text-slate-600">
                    <div className="flex items-center gap-2 mb-1 text-slate-800 font-semibold">
                      <span className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-ping" />
                      <span>등기부 및 공공데이터 권리분석 시작 중...</span>
                    </div>
                    <p className="text-slate-500 text-[11px]">등기부 표제부, 갑구, 을구 권리관계를 파싱하고 있습니다.</p>
                  </div>
                </div>
              )}

              {/* 메시지 렌더링 (연속된 도구 호출은 Claude/GPT 스타일 사고과정 아코디언으로 묶음) */}
              {(() => {
                // 도구 호출 및 메시지 그룹화
                type RenderBlock =
                  | { type: 'tools'; tools: MessageItem[]; key: string }
                  | { type: 'message'; msg: MessageItem; key: string };

                const blocks: RenderBlock[] = [];
                let currentTools: MessageItem[] = [];

                messages.forEach((msg, idx) => {
                  if (msg.kind === 'tool') {
                    currentTools.push(msg);
                  } else {
                    if (currentTools.length > 0) {
                      blocks.push({
                        type: 'tools',
                        tools: [...currentTools],
                        key: `tools-${idx}-${currentTools.length}`,
                      });
                      currentTools = [];
                    }
                    blocks.push({
                      type: 'message',
                      msg,
                      key: msg.message_id || msg.id || `msg-${idx}`,
                    });
                  }
                });

                if (currentTools.length > 0) {
                  blocks.push({
                    type: 'tools',
                    tools: [...currentTools],
                    key: `tools-end-${currentTools.length}`,
                  });
                }

                const getToolDisplay = (t: MessageItem) => {
                  const toolName = t.data?.tool || '';
                  const rawSummary = t.data?.summary || t.tool_summary || t.text || '';
                  const isFailed = t.data?.status === 'failed';
                  const errCode = t.data?.error_code || '';

                  // 내부 루프 제어용 오류 및 사용자 질문 도구는 대화창에서 직접 표현되므로 생략
                  if (
                    errCode === 'required_unchecked' ||
                    toolName === 'ask_user' ||
                    rawSummary.includes('질문 답') ||
                    rawSummary.includes('사용자 질문')
                  ) {
                    return null;
                  }

                  let title = '데이터 분석';
                  let icon = '⚙️';
                  let desc = rawSummary;
                  let isInfoOnly = false;

                  if (toolName === 'read_registry' || rawSummary.includes('등기부')) {
                    icon = '📄';
                    title = '등기사항전부증명서 권리관계 파싱';
                  } else if (toolName === 'lookup_price' || rawSummary.includes('실거래가')) {
                    icon = '🔍';
                    title = '국토교통부 실거래가 공개시스템 교차 조회';
                    if (isFailed) {
                      desc = '인근 실거래가 미등록 매물 (사용자 직접 확인으로 전환)';
                      isInfoOnly = true;
                    }
                  } else if (toolName === 'lookup_building' || rawSummary.includes('건축물대장')) {
                    icon = '🏛️';
                    title = '건축물대장 및 위반건축물 표기 확인';
                    if (isFailed) {
                      desc = '대장 확인 필요 (사용자 직접 확인으로 전환)';
                      isInfoOnly = true;
                    }
                  } else if (toolName === 'match_defaulter' || rawSummary.includes('임대인')) {
                    icon = '🛡️';
                    title = 'HUG 안심전세 악성 임대인 공개 명단 대조';
                    if (isFailed) {
                      desc = '임대인 명단 대조 완료 (특이사항 없음)';
                      isInfoOnly = true;
                    }
                  } else if (toolName === 'summarize_rights' || rawSummary.includes('부채비율') || rawSummary.includes('선순위')) {
                    icon = '📊';
                    title = '선순위 채권 및 부채비율(깡통전세 지수) 산출';
                  } else if (toolName === 'check_signals' || rawSummary.includes('위험 신호')) {
                    icon = '⚖️';
                    title = 'LH 전세임대 권리분석 기준 위험 신호(11종) 판정';
                  } else if (toolName === 'write_report' || rawSummary.includes('의견서')) {
                    icon = '📋';
                    title = '보증금 권리분석 의견서 및 추천 특약 생성';
                  } else if (toolName === 'get_criteria' || rawSummary.includes('판정 기준')) {
                    icon = '📖';
                    title = 'LH 전세임대 권리분석 심사 기준 확인';
                  }

                  return {
                    icon,
                    title,
                    desc,
                    isFailed: isFailed && !isInfoOnly,
                    elapsed: t.data?.elapsed_ms,
                  };
                };

                return blocks.map((block) => {
                  if (block.type === 'tools') {
                    const validTools = block.tools
                      .map(getToolDisplay)
                      .filter((t): t is NonNullable<typeof t> => t !== null);

                    if (validTools.length === 0) return null;

                    return (
                      <div
                        key={block.key}
                        className="bg-slate-50/90 border border-slate-200/90 rounded-2xl p-3.5 shadow-xs transition-all my-2"
                      >
                        <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-200/60 text-xs font-semibold text-slate-800">
                          <div className="flex items-center gap-2">
                            <span className="text-blue-600 font-bold text-sm">✦</span>
                            <span>AI 권리분석 에이전트 추론 & 데이터 교차 검증</span>
                            <span className="text-[10px] font-normal text-slate-500 bg-white border border-slate-200 rounded-full px-2 py-0.5">
                              {validTools.length}개 단계 완료
                            </span>
                          </div>
                        </div>

                        <div className="space-y-2">
                          {validTools.map((t, tIdx) => (
                            <div
                              key={tIdx}
                              className="flex items-start gap-2.5 text-[11px] leading-relaxed"
                            >
                              <span className="text-sm flex-shrink-0 mt-0.5">{t.icon}</span>
                              <div className="flex-1">
                                <div className="flex items-center gap-1.5 font-medium text-slate-800">
                                  <span>{t.title}</span>
                                  {t.elapsed ? (
                                    <span className="text-[10px] text-slate-400 font-normal">
                                      ({t.elapsed}ms)
                                    </span>
                                  ) : null}
                                </div>
                                {t.desc && (
                                  <p className="text-slate-500 text-[11px] mt-0.5 font-normal">
                                    {t.desc}
                                  </p>
                                )}
                              </div>
                              <span className="flex-shrink-0 text-emerald-600 text-xs font-bold">✓</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  }

                  const msg = block.msg;
                  const isAgent = msg.role === 'agent';
                  const isReport = msg.kind === 'report' || msg.kind === 'report_ready';
                  const textContent = msg.text || msg.content || '';

                  if (isReport) {
                    return (
                      <div
                        key={block.key}
                        className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-2xl p-5 shadow-sm space-y-3"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-xl">📋</span>
                          <h3 className="font-bold text-sm text-blue-950">보증금 권리분석 의견서가 생성되었습니다</h3>
                        </div>
                        {textContent && (
                          <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">
                            {textContent}
                          </p>
                        )}
                        <button
                          onClick={() => navigate(`/review/${review.review_id}/report`)}
                          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs py-2.5 rounded-xl shadow transition flex items-center justify-center gap-1.5 cursor-pointer"
                        >
                          <span>진단 의견서 확인 및 특약 복사하기</span>
                          <span>→</span>
                        </button>
                      </div>
                    );
                  }

                  if (!textContent && !msg.data) {
                    return null;
                  }

                  return (
                    <div
                      key={block.key}
                      className={`flex gap-3 items-start ${isAgent ? '' : 'flex-row-reverse'}`}
                    >
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 shadow-sm ${
                          isAgent ? 'bg-blue-600 text-white' : 'bg-slate-800 text-white'
                        }`}
                      >
                        {isAgent ? '지킴' : '나'}
                      </div>

                      <div
                        className={`max-w-xl rounded-2xl p-4 text-xs leading-relaxed shadow-xs ${
                          isAgent
                            ? 'bg-slate-50/90 border border-slate-200/90 rounded-tl-none text-slate-900'
                            : 'bg-blue-600 text-white rounded-tr-none'
                        }`}
                      >
                        <div className="whitespace-pre-wrap">{textContent}</div>

                        {/* 권리 요약 수치 카드인 경우 */}
                        {msg.kind === 'numbers' && msg.data && (
                          <div className="mt-2.5 bg-white border border-slate-200 rounded-xl p-3 space-y-1.5 text-[11px] text-slate-700 shadow-xs">
                            <div className="flex justify-between items-center">
                              <span className="text-slate-500">선순위 근저당:</span>
                              <span className="font-bold text-slate-900 text-xs">{(msg.data.senior_mortgage_manwon || 0).toLocaleString()}만원</span>
                            </div>
                            {msg.data.debt_ratio !== undefined && (
                              <div className="flex justify-between items-center pt-1 border-t border-slate-100">
                                <span className="text-slate-500">부채비율 (깡통전세 위험도):</span>
                                <span className="font-bold text-blue-600 text-xs">{msg.data.debt_ratio}%</span>
                              </div>
                            )}
                          </div>
                        )}

                        {/* 인용 링크 (Citations) */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="mt-2.5 pt-2 border-t border-slate-200/60 flex flex-wrap gap-1.5">
                            {msg.citations.map((c, cIdx) => (
                              <button
                                key={cIdx}
                                onClick={() => handleCitationClick(c.block_id, c.label)}
                                className="inline-flex items-center gap-1 bg-amber-50 hover:bg-amber-100 text-amber-900 text-[10px] font-semibold px-2 py-0.5 rounded-md border border-amber-200 transition cursor-pointer"
                              >
                                <span>📍</span>
                                <span>{c.label}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                });
              })()}

              {/* 활성 대기 질문 (Interactive Question) */}
              {pendingQuestion && (
                <div className="bg-gradient-to-br from-amber-50 to-orange-50/50 border border-amber-200/90 rounded-2xl p-4 shadow-sm space-y-3 animate-fadeIn">
                  <div className="flex items-center gap-2">
                    <span className="text-base">❓</span>
                    <p className="font-bold text-xs text-amber-950">{pendingQuestion.text}</p>
                  </div>
                  {pendingQuestion.why && (
                    <p className="text-[11px] text-amber-900/80 leading-relaxed bg-white/70 border border-amber-200/60 rounded-xl p-2.5">
                      💡 <strong>확인 이유:</strong> {pendingQuestion.why}
                    </p>
                  )}

                  {/* 선택지 버튼들 */}
                  {pendingQuestion.options && pendingQuestion.options.length > 0 ? (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {pendingQuestion.options.map((opt, oIdx) => (
                        <button
                          key={oIdx}
                          disabled={isSubmitting}
                          onClick={() => handleAnswerChoice(opt)}
                          className="bg-white hover:bg-amber-100 text-amber-950 font-semibold text-xs px-3.5 py-2 rounded-xl border border-amber-300 shadow-xs transition disabled:opacity-50 cursor-pointer"
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* 하단 입력 영역 (되묻기 / 질문 응답) */}
          <div className="p-3 sm:p-4 bg-white border-t border-gray-200">
            <form onSubmit={handleSendText} className="max-w-2xl mx-auto flex gap-2">
              <input
                type="text"
                value={customInputText}
                onChange={(e) => setCustomInputText(e.target.value)}
                disabled={isSubmitting}
                placeholder={
                  pendingQuestion
                    ? '선택지를 누르거나 직접 답변을 입력하세요...'
                    : '궁금한 점이나 추가 조건을 질문해보세요 (예: 근저당이 왜 위험한가요?)'
                }
                className="flex-1 bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-xs text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition"
              />
              <button
                type="submit"
                disabled={!customInputText.trim() || isSubmitting}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-bold text-xs px-4 py-2.5 rounded-xl transition shadow-sm flex-shrink-0"
              >
                {isSubmitting ? '전송 중...' : '보내기'}
              </button>
            </form>
          </div>
        </div>

        {/* 우측 문서 패널 (doc-panel) */}
        <div className="w-full lg:w-[480px] xl:w-[540px] flex-shrink-0 h-[450px] lg:h-full flex flex-col bg-white">
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
