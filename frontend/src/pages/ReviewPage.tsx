import React from 'react';
import { useParams } from 'react-router-dom';

export const ReviewPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  return (
    <div data-el="ui-2-review" className="max-w-6xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-2">검토 대화</h1>
      <p className="text-muted mb-4">검토 ID: {id}</p>
      <div className="border border-line rounded-lg p-6 bg-white shadow-sm">
        <p className="text-muted">UI-2 대화 및 문서 패널 뼈대 (슬라이스 B1, B2에서 구현 예정)</p>
      </div>
    </div>
  );
};
