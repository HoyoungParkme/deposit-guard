import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { TopBar } from '../components/TopBar';

interface StepGuide {
  step: number;
  title: string;
  badge: string;
  badgeColor: string;
  summary: string;
  screenshot: string;
  alt: string;
  keyPoints: string[];
  tips: string;
}

export const GuidePage: React.FC = () => {
  const [selectedImg, setSelectedImg] = useState<string | null>(null);

  const steps: StepGuide[] = [
    {
      step: 1,
      badge: 'Step 1 · 입력 단계',
      badgeColor: 'bg-blue-100 text-blue-800 border-blue-200',
      title: '등기부등본 등록 & 실전 사례 1초 로드',
      summary:
        '인터넷등기소나 공인중개사에게 받은 등기사항전부증명서(PDF·사진)를 올리거나, 준비된 3가지 실제 대표 사례(다가구 깡통전세, 근생빌라, 안심 오피스텔)를 1클릭으로 즉시 체험합니다.',
      screenshot: '/guide/guide_step1_start.png',
      alt: '보증금지킴 메인 화면 및 등기부 업로드 화면',
      keyPoints: [
        'PDF 및 사진(JPG, PNG) 자동 파싱 및 OCR 지원 (100% 브라우저 내 안전 처리)',
        '계약 형태(전세/월세) 및 희망 보증금·월세 입력',
        '서류가 없어도 3가지 실전 사례로 1초 만에 즉시 모의 진단 가능',
        '모든 파일은 24시간 후 자동 영구 파기되어 개인정보 안심 보장',
      ],
      tips: '💡 팁: 대법원 인터넷등기소(iros.go.kr)에서 700원에 열람용 등기사항전부증명서(말소사항포함)를 PDF로 다운로드해 넣으시면 가장 정확합니다.',
    },
    {
      step: 2,
      badge: 'Step 2 · AI 분석 단계',
      badgeColor: 'bg-indigo-100 text-indigo-800 border-indigo-200',
      title: 'Gemini 2.5 Flash 실시간 권리분석 & 투명한 추론 과정',
      summary:
        'AI가 등기부의 표제부·갑구·을구를 정밀 분석하며, 최신 생성형 AI(ChatGPT, Claude, Gemini) 스타일의 [생각하는 과정] 아코디언을 통해 국토부 실거래가 조회 및 LH/HUG 심사기준 매칭 과정을 투명하게 공개합니다.',
      screenshot: '/guide/guide_step2_chat.png',
      alt: 'AI 대화형 권리분석 및 생각하는 과정 아코디언 화면',
      keyPoints: [
        'AI 추론 과정(Thinking Process)을 실시간으로 펼쳐보고 법률 근거 확인 가능',
        '국토교통부 실거래가 공공 API와 매칭하여 현실적인 매매 시세 추정',
        '대화형 채팅을 통해 "선순위 보증금이 높으면 어떻게 해야 하나요?", "보증보험 가입 요건은?" 등 실시간 법률 질의응답',
        '선순위 채권액, 근저당 채권최고액의 실제 원금 환산 계산',
      ],
      tips: '💡 팁: 채팅창 상단의 [생각 과정 / 도구 호출] 접기를 클릭하면 AI가 어떤 법률 조항과 공공데이터를 근거로 판단했는지 한눈에 검증할 수 있습니다.',
    },
    {
      step: 3,
      badge: 'Step 3 · 진단서 및 행동 단계',
      badgeColor: 'bg-emerald-100 text-emerald-800 border-emerald-200',
      title: '보증금 진단 종합 의견서 & 계약서 6대 방어 특약 복사',
      summary:
        'LH 공공임대 심사원 수준의 정밀 진단서가 발행됩니다. 깡통전세 부채비율 계산, 11대 위험신호 탐지, 계약서에 바로 넣을 수 있는 6대 맞춤형 특약(원클릭 복사)과 단계별 13대 체크리스트를 제공합니다.',
      screenshot: '/guide/guide_step3_report.png',
      alt: '보증금 진단 종합 의견서 및 6대 특약 복사 화면',
      keyPoints: [
        '정확한 부채비율 공식: (선순위 채권 + 내 보증금) ÷ 추정 시세 × 100',
        'HUG 전세보증금반환보증 가입 가능 여부(90% 안전선 기준) 즉시 판정',
        '공인중개사에게 복사해서 그대로 전달할 수 있는 법무부 표준 6대 맞춤 특약안 원클릭 복사',
        '계약 전 → 계약 당일 → 잔금/입주 단계별 13가지 필수 행동 체크리스트',
        '상단 [공유 링크 복사]를 통해 부모님, 배우자, 중개사에게 진단 결과 간편 공유',
      ],
      tips: '💡 팁: 특약 섹션의 [특약 복사] 버튼을 누른 후 공인중개사에게 문자나 카톡으로 보내 "이 특약을 계약서에 꼭 넣어주세요"라고 요청하시면 전세사기를 완벽히 방어할 수 있습니다.',
    },
    {
      step: 4,
      badge: 'Step 4 · 공공 기준 검증',
      badgeColor: 'bg-amber-100 text-amber-800 border-amber-200',
      title: 'LH/HUG 공공임대 심사 기준표 및 11대 위험신호 매트릭스',
      summary:
        '단순한 AI의 주관적 추측이 아닌, 한국토지주택공사(LH) 전세임대 권리분석 세부 지침과 주택도시보증공사(HUG) 보증 요건, 주택임대차보호법에 명시된 객관적인 법적 심사 기준을 누구나 투명하게 열람할 수 있습니다.',
      screenshot: '/guide/guide_step4_criteria.png',
      alt: 'LH 권리분석 심사 기준 및 11대 위험신호 매트릭스 화면',
      keyPoints: [
        '11대 위험 신호: 신탁등기, 임차권등기명령 이력, 선순위 근저당 과다, 위반건축물, 압류/가압류 등 전수 분류',
        '전국 지역별 소액임차인 최우선변제금 기준 금액 및 적용 시점별 법정 한도표 제공',
        '아파트, 다세대, 다가구, 오피스텔 등 건물 유형별 필수 점검 사항 안내',
      ],
      tips: '💡 팁: 상단 메뉴의 [판정 기준]을 언제든지 클릭하여 각 위험 신호의 법적 효력과 대법원 판례 해설을 찾아볼 수 있습니다.',
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <TopBar />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8 sm:py-12 space-y-12">
        {/* 상단 히어로 헤더 */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-blue-100 text-blue-800 text-xs font-bold border border-blue-200">
            <span>🛡️</span>
            <span>보증금지킴 서비스 가이드 & 작동 원리</span>
          </div>
          <h1 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight">
            내 소중한 전세 보증금, <br className="hidden sm:inline" />
            <span className="text-blue-600">어떻게 지켜주는지</span> 알려드립니다
          </h1>
          <p className="text-sm sm:text-base text-slate-700 leading-relaxed">
            복잡한 등기부등본 용어와 깡통전세 계산이 어려우셨나요? <br className="hidden sm:inline" />
            등기부 1장이면 LH 심사관 수준의 권리분석과 계약서용 방어 특약까지 1분 만에 완성됩니다.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <Link
              to="/"
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm px-5 py-2.5 rounded-xl shadow-sm hover:shadow transition flex items-center gap-2"
            >
              <span>🚀</span>
              <span>지금 무료로 진단 시작하기</span>
            </Link>
            <Link
              to="/criteria"
              className="bg-white hover:bg-slate-100 text-slate-700 font-semibold text-sm px-4 py-2.5 rounded-xl border border-slate-300 transition"
            >
              ⚖️ LH 심사 기준표 보기
            </Link>
          </div>
        </div>

        {/* 3대 문제와 해결책 카드 */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-6 sm:p-8 shadow-xs">
          <div className="text-center max-w-xl mx-auto mb-8">
            <span className="text-xs font-bold text-indigo-600 bg-indigo-50 border border-indigo-200/60 px-3 py-1 rounded-full">
              Why Deposit Guard?
            </span>
            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 mt-2">
              어떤 문제를 어떻게 해결하나요?
            </h2>
            <p className="text-sm text-slate-600 mt-1">
              기존 부동산 시장의 정보 비대칭과 전세사기 사각지대를 기술로 해소합니다.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="bg-gradient-to-b from-rose-50/50 to-white border border-rose-200/80 rounded-xl p-5 space-y-3">
              <div className="text-2xl">⚠️ 1. 깡통전세 공포</div>
              <h3 className="font-bold text-slate-900 text-sm">부채비율 계산의 어려움</h3>
              <p className="text-sm text-slate-700 leading-relaxed">
                집값 대비 근저당과 앞선 보증금이 얼마인지 몰라 경매로 넘어갔을 때 내 보증금을 돌려받을 수 있는지 불안합니다.
              </p>
              <div className="pt-2 border-t border-rose-100 text-sm font-medium text-blue-700 bg-blue-50/50 p-2.5 rounded-lg">
                💡 <strong>해결</strong>: 국토부 실거래가 매매가와 선순위 채권을 취합하여 LH 90% 안전 기준 부채비율을 자동 계산합니다.
              </div>
            </div>

            <div className="bg-gradient-to-b from-amber-50/50 to-white border border-amber-200/80 rounded-xl p-5 space-y-3">
              <div className="text-2xl">💣 2. 숨겨진 법적 지뢰</div>
              <h3 className="font-bold text-slate-900 text-sm">신탁등기·임차권등기</h3>
              <p className="text-sm text-slate-700 leading-relaxed">
                신탁회사 동의 없는 계약은 무효이며, 이전 세입자에게 보증금을 돌려주지 않은 임대인은 다시 사고를 냅니다.
              </p>
              <div className="pt-2 border-t border-amber-100 text-sm font-medium text-indigo-700 bg-indigo-50/50 p-2.5 rounded-lg">
                💡 <strong>해결</strong>: 11대 핵심 위험 신호(신탁, 임차권등기, 압류, 불법개조 등)를 전수 자동 검출하여 경고합니다.
              </div>
            </div>

            <div className="bg-gradient-to-b from-emerald-50/50 to-white border border-emerald-200/80 rounded-xl p-5 space-y-3">
              <div className="text-2xl">📝 3. 무방비 계약서</div>
              <h3 className="font-bold text-slate-900 text-sm">말뿐인 구두 약속의 한계</h3>
              <p className="text-sm text-slate-700 leading-relaxed">
                "문제없다"는 중개인 말만 믿고 도장을 찍었다가 보증보험이 거절되거나 당일 대출이 발생하면 보호받지 못합니다.
              </p>
              <div className="pt-2 border-t border-emerald-100 text-sm font-medium text-emerald-700 bg-emerald-50/50 p-2.5 rounded-lg">
                💡 <strong>해결</strong>: 법무부 표준 특약 기반 6대 방어 특약문구를 생성해 계약서에 복사·붙여넣을 수 있게 제공합니다.
              </div>
            </div>
          </div>
        </div>

        {/* 4단계 시각적 사용 흐름 (스크린샷 포함) */}
        <div className="space-y-10">
          <div className="text-center max-w-xl mx-auto">
            <span className="text-xs font-bold text-blue-600 bg-blue-50 border border-blue-200/60 px-3 py-1 rounded-full">
              실제 화면으로 보는 이용 매뉴얼
            </span>
            <h2 className="text-2xl font-bold text-slate-900 mt-2">
              클릭 1번으로 시작하는 4단계 안전 진단
            </h2>
            <p className="text-sm text-slate-600 mt-1">
              아래 각 단계의 실제 서비스 캡처 화면을 확인해보세요. (이미지 클릭 시 크게 보기)
            </p>
          </div>

          <div className="space-y-12">
            {steps.map((s) => (
              <div
                key={s.step}
                className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs hover:shadow-md transition duration-200"
              >
                {/* 상단 헤더 바 */}
                <div className="px-6 py-4 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3 bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm shadow-xs">
                      {s.step}
                    </span>
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-md border ${s.badgeColor}`}>
                      {s.badge}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500 font-medium">Deposit Guard Walkthrough</span>
                </div>

                {/* 본문 콘텐츠 */}
                <div className="p-6 sm:p-8 space-y-6">
                  <div>
                    <h3 className="text-lg sm:text-xl font-extrabold text-slate-900 mb-2">
                      {s.title}
                    </h3>
                    <p className="text-base text-slate-700 leading-relaxed">{s.summary}</p>
                  </div>

                  {/* 실제 스크린샷 미리보기 */}
                  <div
                    onClick={() => setSelectedImg(s.screenshot)}
                    className="relative group cursor-pointer overflow-hidden rounded-xl border border-slate-200 bg-slate-100 shadow-inner"
                  >
                    <img
                      src={s.screenshot}
                      alt={s.alt}
                      className="w-full h-auto object-cover object-top max-h-[520px] group-hover:scale-[1.008] transition duration-300"
                    />
                    <div className="absolute inset-0 bg-slate-900/30 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-2 text-white font-bold text-sm">
                      <span>🔍 클릭하여 원본 크기로 확대하기</span>
                    </div>
                  </div>

                  {/* 주요 기능 체크포인트 */}
                  <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-5 space-y-2.5">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <span>✨</span>
                      <span>이 단계의 핵심 기능</span>
                    </h4>
                    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-slate-700">
                      {s.keyPoints.map((point, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-blue-500 font-bold mt-0.5">✓</span>
                          <span>{point}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* 활용 팁 */}
                  <div className="text-sm text-slate-700 bg-blue-50/60 border border-blue-200/50 rounded-lg p-3.5 leading-relaxed">
                    {s.tips}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 자주 묻는 질문 (FAQ) */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 shadow-xs">
          <h2 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-2">
            <span>❓</span>
            <span>자주 묻는 질문 (FAQ)</span>
          </h2>

          <div className="space-y-4 text-sm">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
              <h3 className="font-bold text-slate-900">Q. 등기부등본 파일이 없는데 어떻게 테스트하나요?</h3>
              <p className="text-slate-700 leading-relaxed text-sm">
                메인 페이지 시작 화면의 <strong>‘등기부 파일이 없다면? 실제 사례로 체험하기’</strong> 섹션에서 [신길동 다가구(깡통전세 위험)], [봉천동 근생빌라(대출불가)], [역삼동 오피스텔(안심매물)] 카드를 클릭하시면 별도의 파일 업로드 없이 1초 만에 실제 데이터로 검토를 진행할 수 있습니다.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
              <h3 className="font-bold text-slate-900">Q. 등기부등본은 어디서 발급받나요?</h3>
              <p className="text-slate-700 leading-relaxed text-sm">
                대법원 인터넷등기소(www.iros.go.kr)에서 주소 검색 후 700원에 [등기사항전부증명서(말소사항포함)]를 열람하여 PDF로 저장할 수 있습니다. 공인중개사에게 매물을 문의할 때 전달받은 등기부 사진이나 PDF 파일을 그대로 등록하셔도 됩니다.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
              <h3 className="font-bold text-slate-900">Q. 비용이나 회원가입이 필요한가요?</h3>
              <p className="text-slate-700 leading-relaxed text-sm">
                별도의 회원가입이나 로그인 없이 100% 무료로 모든 권리분석 및 특약 생성 기능을 이용하실 수 있습니다. 심사위원 및 모든 이용자가 언제든지 편리하게 체험 가능합니다.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
              <h3 className="font-bold text-slate-900">Q. 여기서 나온 특약은 법적으로 효력이 있나요?</h3>
              <p className="text-slate-700 leading-relaxed text-sm">
                네. 본 서비스의 6대 맞춤 특약은 주택임대차보호법 및 법무부 표준 주택임대차계약서 특약 조항을 바탕으로 작성되었습니다. 진단서의 [특약 복사] 버튼을 누른 후 계약서의 특약사항 란에 그대로 기재하시면 계약 당사자 간의 법적 구속력을 가집니다.
              </p>
            </div>
          </div>
        </div>

        {/* 하단 CTA 배너 */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 text-white rounded-2xl p-6 sm:p-10 text-center space-y-4 shadow-md">
          <h2 className="text-2xl sm:text-3xl font-black">
            불안한 전세 계약, 지금 1분 만에 지키세요
          </h2>
          <p className="text-blue-200 text-sm sm:text-base max-w-xl mx-auto">
            국토부 실거래가와 LH 전세임대 심사기준으로 깡통전세와 법적 지뢰를 사전에 차단합니다.
          </p>
          <div className="pt-2">
            <Link
              to="/"
              className="inline-flex items-center gap-2 bg-white text-blue-700 font-bold text-sm px-6 py-3 rounded-xl shadow hover:bg-blue-50 transition transform hover:-translate-y-0.5"
            >
              <span>🛡️</span>
              <span>지금 무료로 안전 진단하기</span>
            </Link>
          </div>
        </div>
      </main>

      {/* 이미지 확대 모달 */}
      {selectedImg && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 backdrop-blur-xs cursor-pointer"
          onClick={() => setSelectedImg(null)}
        >
          <div className="relative max-w-5xl max-h-[90vh] overflow-auto rounded-xl bg-white p-2 shadow-2xl">
            <img src={selectedImg} alt="확대 화면" className="w-full h-auto rounded-lg" />
            <div className="absolute top-4 right-4 bg-slate-900/80 text-white text-xs px-3 py-1.5 rounded-full font-bold">
              닫기 ✕
            </div>
          </div>
        </div>
      )}

      {/* 푸터 */}
      <footer className="w-full border-t border-slate-200 bg-white py-6 px-4 text-center text-sm text-slate-500">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>보증금지킴은 법률 상담이나 공인중개사를 대체하지 않는 참고용 권리분석 의견서입니다.</p>
          <p className="text-[11px]">
            출처: 국토교통부 · LH 한국토지주택공사 · HUG 주택도시보증공사 · 대법원 인터넷등기소
          </p>
        </div>
      </footer>
    </div>
  );
};
