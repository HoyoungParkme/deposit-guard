import React from 'react';
import { Link } from 'react-router-dom';
import { ReviewSubject, ReviewCounters } from '../api/client';

interface TopBarProps {
  subject?: ReviewSubject;
  counters?: ReviewCounters;
}

const buildingTypeNames: Record<string, string> = {
  apartment: '아파트',
  multi_family_unit: '다세대·연립',
  multi_household: '다가구',
  officetel: '오피스텔',
  other: '주택',
};

export const TopBar: React.FC<TopBarProps> = ({ subject, counters }) => {
  const formatSec = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m > 0 ? `${m}분 ${s}초` : `${s}초`;
  };

  return (
    <header className="w-full border-b border-gray-200 bg-white px-4 py-3 sticky top-0 z-50 shadow-sm" data-el="1">
      <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
        {/* 서비스명 및 브랜드 */}
        <div className="flex items-center gap-3">
          <Link to="/" className="text-xl font-bold text-blue-600 tracking-tight flex items-center gap-1.5 hover:text-blue-700">
            <span className="bg-blue-600 text-white rounded-lg px-2 py-0.5 text-sm">지킴</span>
            <span>보증금지킴</span>
          </Link>
          <span className="text-xs text-gray-400 border-l border-gray-300 pl-3 hidden sm:inline">
            LH 전세임대 권리분석 기준
          </span>
        </div>

        {/* 검토 대상 요약 (검토 화면일 때) */}
        {subject && (
          <div className="hidden md:flex items-center gap-2 text-sm text-gray-700 bg-gray-50 px-3 py-1.5 rounded-full border border-gray-200">
            <span className="font-semibold text-gray-900">{subject.region || '지역 미확인'}</span>
            <span className="text-gray-300">·</span>
            <span>{buildingTypeNames[subject.building_type] || '주택'}</span>
            <span className="text-gray-300">·</span>
            <span className="font-medium text-blue-600">
              {subject.contract_type === 'jeonse' ? '전세' : '월세'} {subject.deposit_manwon.toLocaleString()}만원
            </span>
          </div>
        )}

        {/* 우측 링크 및 진행 카운터 */}
        <div className="flex items-center gap-4 text-sm">
          {counters && (
            <div className="hidden sm:flex items-center gap-3 text-xs text-gray-500">
              <span>도구 {counters.tool_calls}회</span>
              <span>질문 {counters.questions_asked}회</span>
              <span>{formatSec(counters.elapsed_sec)} 경과</span>
            </div>
          )}

          <Link
            to="/guide"
            className="text-gray-600 hover:text-gray-900 font-medium px-2 py-1 rounded hover:bg-gray-100 transition flex items-center gap-1"
          >
            <span>📖</span>
            <span>이용 가이드</span>
          </Link>

          <Link
            to="/criteria"
            className="text-gray-600 hover:text-gray-900 font-medium px-2 py-1 rounded hover:bg-gray-100 transition"
          >
            판정 기준
          </Link>

          {subject && (
            <Link
              to="/"
              className="text-xs font-semibold text-gray-600 border border-gray-300 rounded px-2.5 py-1.5 hover:bg-gray-50 transition"
            >
              새 검토
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};
