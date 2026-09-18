import React from 'react';

export const StartPage: React.FC = () => {
  return (
    <div data-el="ui-1-start" className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-4">보증금지킴</h1>
      <p className="text-muted mb-8">
        부동산 등기부등본을 올려 보증금 안전도를 대화형 AI로 진단받으세요.
      </p>
      <div className="border border-line rounded-lg p-6 bg-white shadow-sm">
        <p className="text-muted">UI-1 시작 화면 뼈대 (슬라이스 B1에서 구현 예정)</p>
      </div>
    </div>
  );
};
