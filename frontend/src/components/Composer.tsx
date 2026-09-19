import React, { useState, useRef, useEffect } from 'react';
import { CreateReviewParams, SampleCase } from '../api/client';

interface ComposerProps {
  initialValues?: Partial<CreateReviewParams>;
  selectedSample?: SampleCase | null;
  onClearSample?: () => void;
  onSubmit: (params: CreateReviewParams) => void;
  isLoading?: boolean;
  errorMessage?: string | null;
}

export const Composer: React.FC<ComposerProps> = ({
  initialValues,
  selectedSample,
  onClearSample,
  onSubmit,
  isLoading = false,
  errorMessage,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [deposit, setDeposit] = useState<string>(
    initialValues?.deposit_manwon ? initialValues.deposit_manwon.toString() : ''
  );
  const [contractType, setContractType] = useState<'jeonse' | 'monthly'>(
    initialValues?.contract_type || 'jeonse'
  );
  const [counterpartyName, setCounterpartyName] = useState<string>(
    initialValues?.counterparty_name || ''
  );
  const [showCounterparty, setShowCounterparty] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (selectedSample) {
      setDeposit(selectedSample.deposit_manwon.toString());
      setContractType(selectedSample.contract_type);
      setFile(null);
    }
  }, [selectedSample]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      if (onClearSample) onClearSample();
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      if (onClearSample) onClearSample();
    }
  };

  const formatDepositKorean = (valStr: string) => {
    const num = parseInt(valStr, 10);
    if (isNaN(num) || num <= 0) return '';
    const uk = Math.floor(num / 10000);
    const man = num % 10000;
    if (uk > 0 && man > 0) return `${uk}억 ${man.toLocaleString()}만원`;
    if (uk > 0) return `${uk}억원`;
    return `${man.toLocaleString()}만원`;
  };

  const hasSource = !!selectedSample || !!file;
  const depositNum = parseInt(deposit, 10);
  const hasValidDeposit = !isNaN(depositNum) && depositNum >= 1;
  const canSubmit = hasSource && hasValidDeposit && !isLoading;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    onSubmit({
      deposit_manwon: depositNum,
      contract_type: contractType,
      sample_id: selectedSample?.sample_id,
      counterparty_name: counterpartyName.trim() || undefined,
      file: file || undefined,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white border-2 border-gray-200 rounded-2xl p-5 shadow-sm transition hover:border-gray-300"
      data-el="3"
    >
      {/* 파일 드롭존 */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition flex flex-col items-center justify-center min-h-[140px] ${
          isDragOver
            ? 'border-blue-500 bg-blue-50'
            : hasSource
            ? 'border-blue-400 bg-blue-50/40'
            : 'border-gray-300 bg-gray-50 hover:bg-gray-100/70'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          onChange={handleFileChange}
          className="hidden"
        />

        {selectedSample ? (
          <div className="flex flex-col items-center gap-1">
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700 bg-blue-100 px-2.5 py-1 rounded-full">
              ✓ 예시 등기부 선택됨
            </span>
            <p className="font-bold text-gray-900 mt-1">{selectedSample.title}</p>
            <p className="text-xs text-gray-600">{selectedSample.summary}</p>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (onClearSample) onClearSample();
              }}
              className="text-xs text-gray-600 hover:text-red-500 underline mt-2"
            >
              직접 파일 올리기로 변경
            </button>
          </div>
        ) : file ? (
          <div className="flex flex-col items-center gap-1">
            <span className="text-2xl">📄</span>
            <p className="font-semibold text-gray-900 text-sm">{file.name}</p>
            <p className="text-xs text-gray-600">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            <span className="text-xs text-blue-600 font-medium underline mt-1">다른 파일 선택</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1.5">
            <span className="text-3xl text-gray-400">📄</span>
            <p className="text-base font-semibold text-gray-800">
              등기부등본 PDF를 끌어다 놓거나 클릭해 첨부하세요
            </p>
            <p className="text-xs text-gray-600">PDF, JPG, PNG · 10MB, 20쪽 이하만 가능</p>
          </div>
        )}
      </div>

      {/* 입력 폼 필드들 */}
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* 보증금 입력란 */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">
            보증금 (만원)
            {deposit && <span className="ml-2 font-normal text-blue-600">{formatDepositKorean(deposit)}</span>}
          </label>
          <div className="relative">
            <input
              type="number"
              min="1"
              step="1"
              value={deposit}
              onChange={(e) => setDeposit(e.target.value)}
              placeholder="예: 20000 (2억원)"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <span className="absolute right-3 top-2 text-xs text-gray-600">만원</span>
          </div>
        </div>

        {/* 계약 형태 선택 */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">계약 형태</label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setContractType('jeonse')}
              className={`py-2 text-sm rounded-lg font-medium border transition ${
                contractType === 'jeonse'
                  ? 'bg-blue-50 border-blue-600 text-blue-700 font-semibold'
                  : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              전세
            </button>
            <button
              type="button"
              onClick={() => setContractType('monthly')}
              className={`py-2 text-sm rounded-lg font-medium border transition ${
                contractType === 'monthly'
                  ? 'bg-blue-50 border-blue-600 text-blue-700 font-semibold'
                  : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              월세
            </button>
          </div>
        </div>
      </div>

      {/* 임대인 이름 접힘/펼침 */}
      <div className="mt-3">
        {!showCounterparty ? (
          <button
            type="button"
            onClick={() => setShowCounterparty(true)}
            className="text-xs text-gray-600 hover:text-gray-800 flex items-center gap-1 font-medium"
          >
            <span>+ 임대인(집주인) 이름 입력 (선택: 소유자 일치 확인)</span>
          </button>
        ) : (
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-semibold text-gray-700">임대인 이름 (선택)</label>
              <button
                type="button"
                onClick={() => {
                  setShowCounterparty(false);
                  setCounterpartyName('');
                }}
                className="text-xs text-gray-600 hover:text-gray-800"
              >
                닫기
              </button>
            </div>
            <input
              type="text"
              value={counterpartyName}
              onChange={(e) => setCounterpartyName(e.target.value)}
              placeholder="계약서의 임대인 성명 또는 법인명"
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}
      </div>

      {/* 에러 메시지 표시 */}
      {errorMessage && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs font-medium">
          {errorMessage}
        </div>
      )}

      {/* 하단 버튼 및 안내 줄 */}
      <div className="mt-4 pt-3 border-t border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="text-xs text-gray-600" data-el="3b">
          {!hasSource ? (
            <span>등기부 파일을 첨부하거나 아래 예시 카드를 선택하세요</span>
          ) : !hasValidDeposit ? (
            <span>보증금 금액을 입력해 주세요</span>
          ) : (
            <span className="text-blue-600 font-medium">검토 준비 완료 · 로그인 없이 즉시 시작</span>
          )}
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className={`w-full sm:w-auto px-6 py-2.5 rounded-xl font-bold text-sm min-h-[44px] transition shadow-sm ${
            canSubmit
              ? 'bg-blue-600 text-white hover:bg-blue-700 active:scale-[0.99]'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }`}
        >
          {isLoading ? '등기부 분석 중...' : '검토 시작하기 →'}
        </button>
      </div>
    </form>
  );
};
