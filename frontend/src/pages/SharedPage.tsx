import React from 'react';
import { useParams } from 'react-router-dom';

export const SharedPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();

  return (
    <div data-el="ui-5-shared" className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-2">공유된 보증금 진단 의견서</h1>
      <p className="text-muted mb-4">공유 토큰: {token}</p>
      <div className="border border-line rounded-lg p-6 bg-white shadow-sm">
        <p className="text-muted">UI-5 마스킹된 공유 의견서 뼈대 (슬라이스 B4에서 구현 예정)</p>
      </div>
    </div>
  );
};
