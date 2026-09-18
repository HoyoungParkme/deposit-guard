import React from 'react';
import { useParams } from 'react-router-dom';

export const ReportPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  return (
    <div data-el="ui-3-report" className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-2">보증금 진단 의견서</h1>
      <p className="text-muted mb-4">검토 ID: {id}</p>
      <div className="border border-line rounded-lg p-6 bg-white shadow-sm">
        <p className="text-muted">UI-3 의견서 단독 및 인쇄용 뼈대 (슬라이스 B2에서 구현 예정)</p>
      </div>
    </div>
  );
};
