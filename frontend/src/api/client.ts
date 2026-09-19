/**
 * API 클라이언트.
 * 근거: JSD-DOM-002 1장, JSD-API-001, JSD-UI-001
 */

export interface SampleCase {
  sample_id: string;
  title: string;
  summary: string;
  region: string;
  deposit_manwon: number;
  contract_type: 'jeonse' | 'monthly';
}

export interface ReviewSubject {
  building_type: string;
  deposit_manwon: number;
  contract_type: 'jeonse' | 'monthly';
  region: string;
}

export interface ReviewCounters {
  tool_calls: number;
  questions_asked: number;
  asks_used: number;
  elapsed_sec: number;
  cost_krw: number;
}

export interface ReviewDocumentItem {
  document_id: string;
  kind: 'building' | 'land' | 'collective';
  label: string;
  page_count?: number;
}

export interface QuestionData {
  question_id: string;
  kind: string;
  text: string;
  why?: string;
  input_type: 'choice' | 'text' | 'money' | 'file';
  options?: string[];
  help_url?: string;
  asked_no?: number;
}

export interface ReviewView {
  review_id: string;
  status: 'created' | 'running' | 'waiting_user' | 'done' | 'failed' | 'expired';
  subject: ReviewSubject;
  counters: ReviewCounters;
  pending_question: QuestionData | null;
  documents: ReviewDocumentItem[];
  has_report: boolean;
  expires_at: string;
}

export interface MessageItem {
  id?: string;
  message_id?: string;
  seq: number;
  role: 'agent' | 'user' | 'system';
  kind: string;
  text?: string;
  content?: string;
  data?: any;
  created_at?: string;
  tool_name?: string;
  tool_summary?: string;
  question_id?: string;
  question?: QuestionData;
  citations?: Array<{ block_id: string; label: string; excerpt?: string }>;
}

export interface RiskSignalItem {
  code: string;
  severity: 'danger' | 'caution';
  label: string;
  description?: string;
  source?: string;
  source_date?: string;
}

export interface ClauseItem {
  code?: string;
  title: string;
  body?: string;
  text?: string;
  source?: string;
  reason?: string;
  filled?: boolean;
}

export interface TodoItem {
  phase: 'before_contract' | 'closing' | 'move_in' | string;
  title: string;
  text: string;
}

export interface ReportData {
  review_id: string;
  grade: 'safe' | 'caution' | 'danger';
  grade_label?: string;
  summary: string;
  reasons: string[];
  debt_ratio?: number;
  price_manwon?: number;
  senior_debt_manwon?: number;
  deposit_manwon?: number;
  priority_repayment_manwon?: number;
  signals?: RiskSignalItem[];
  clauses?: ClauseItem[];
  todos?: TodoItem[];
  entries?: Array<{
    entry_id: string;
    section: string;
    rank_no: string;
    purpose: string;
    amount_manwon?: number;
    holder?: string;
  }>;
  created_at: string;
}

export interface SharedView {
  report: ReportData;
  subject: {
    region_short?: string;
    building_type?: string;
    deposit_manwon?: number;
    contract_type?: string;
    reviewed_at?: string;
  };
  expires_at: string;
}

export interface CreateReviewParams {
  deposit_manwon: number;
  contract_type: 'jeonse' | 'monthly';
  sample_id?: string;
  counterparty_name?: string;
  file?: File;
}

export interface CreateReviewResponse {
  review_id: string;
  status: string;
  is_sample: boolean;
  expires_at: string;
}

export class ApiError extends Error {
  constructor(
    public code: string,
    public detail: string,
    public field?: string | null,
    public status?: number,
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errJson: any;
    try {
      errJson = await res.json();
    } catch {
      throw new ApiError('internal', '서버 통신 오류가 발생했습니다.', null, res.status);
    }
    throw new ApiError(
      errJson.code || 'internal',
      errJson.detail || '요청 처리 중 오류가 발생했습니다.',
      errJson.field,
      res.status,
    );
  }
  return res.json();
}

export async function getSamples(): Promise<SampleCase[]> {
  const res = await fetch('/api/samples');
  const data = await handleResponse<{ samples: SampleCase[] }>(res);
  return data.samples;
}

export async function createReview(params: CreateReviewParams): Promise<CreateReviewResponse> {
  const formData = new FormData();
  formData.append('deposit_manwon', params.deposit_manwon.toString());
  formData.append('contract_type', params.contract_type);

  if (params.sample_id) {
    formData.append('sample_id', params.sample_id);
  }
  if (params.counterparty_name) {
    formData.append('counterparty_name', params.counterparty_name);
  }
  if (params.file) {
    formData.append('file', params.file);
  }

  const res = await fetch('/api/reviews', {
    method: 'POST',
    body: formData,
  });
  return handleResponse<CreateReviewResponse>(res);
}

export async function getReview(reviewId: string): Promise<ReviewView> {
  const res = await fetch(`/api/reviews/${reviewId}`);
  return handleResponse<ReviewView>(res);
}

export async function getDocuments(reviewId: string): Promise<ReviewDocumentItem[]> {
  const res = await fetch(`/api/reviews/${reviewId}/documents`);
  const data = await handleResponse<{ documents: ReviewDocumentItem[] }>(res);
  return data.documents;
}

export async function getDocumentHtml(reviewId: string, documentId: string): Promise<string> {
  const res = await fetch(`/api/reviews/${reviewId}/documents/${documentId}`);
  if (!res.ok) {
    await handleResponse(res);
  }
  return res.text();
}

export async function listMessages(reviewId: string, afterSeq: number = 0): Promise<{ messages: MessageItem[]; next_seq: number; status: string }> {
  const res = await fetch(`/api/reviews/${reviewId}/messages?after_seq=${afterSeq}`);
  return handleResponse<{ messages: MessageItem[]; next_seq: number; status: string }>(res);
}

export async function postMessage(
  reviewId: string,
  payload: {
    kind: 'answer' | 'ask';
    question_id?: string;
    text?: string;
    choice?: string;
    file?: File;
  },
): Promise<{ message_id: string; seq: number }> {
  let res: Response;
  if (payload.file) {
    const formData = new FormData();
    formData.append('kind', payload.kind);
    if (payload.question_id) formData.append('question_id', payload.question_id);
    if (payload.text) formData.append('text', payload.text);
    if (payload.choice) formData.append('choice', payload.choice);
    formData.append('file', payload.file);

    res = await fetch(`/api/reviews/${reviewId}/messages`, {
      method: 'POST',
      body: formData,
    });
  } else {
    res = await fetch(`/api/reviews/${reviewId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  }
  return handleResponse<{ message_id: string; seq: number }>(res);
}

export async function deleteReview(reviewId: string): Promise<void> {
  const res = await fetch(`/api/reviews/${reviewId}`, {
    method: 'DELETE',
  });
  if (!res.ok && res.status !== 204) {
    await handleResponse(res);
  }
}

export async function getReport(reviewId: string): Promise<ReportData> {
  const res = await fetch(`/api/reviews/${reviewId}/report`);
  return handleResponse<ReportData>(res);
}

export async function overrideValues(
  reviewId: string,
  payload: {
    price_manwon?: number | null;
    entries?: Array<{ entry_id: string; amount_manwon: number }>;
  },
): Promise<ReportData> {
  const res = await fetch(`/api/reviews/${reviewId}/values`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<ReportData>(res);
}

export async function createShareLink(reviewId: string): Promise<{ token: string; url: string; expires_at: string }> {
  const res = await fetch(`/api/reviews/${reviewId}/shares`, {
    method: 'POST',
  });
  return handleResponse<{ token: string; url: string; expires_at: string }>(res);
}

export async function getSharedView(token: string): Promise<SharedView> {
  const res = await fetch(`/api/shares/${token}`);
  return handleResponse<SharedView>(res);
}

export async function getCriteria(topic?: string, signalCode?: string): Promise<any> {
  const params = new URLSearchParams();
  if (topic) params.append('topic', topic);
  if (signalCode) params.append('signal_code', signalCode);
  const query = params.toString() ? `?${params.toString()}` : '';
  const res = await fetch(`/api/criteria${query}`);
  return handleResponse<any>(res);
}

export async function getBlockUsages(reviewId: string, blockId: string): Promise<{ block_id: string; excerpt: string; used_in: any[] }> {
  const res = await fetch(`/api/reviews/${reviewId}/blocks/${blockId}`);
  return handleResponse<{ block_id: string; excerpt: string; used_in: any[] }>(res);
}
