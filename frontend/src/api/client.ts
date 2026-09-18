/**
 * API 클라이언트.
 * 근거: JSD-DOM-002 1장, JSD-API-001
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

export interface ReviewView {
  review_id: string;
  status: 'created' | 'running' | 'waiting_user' | 'done' | 'failed' | 'expired';
  subject: ReviewSubject;
  counters: ReviewCounters;
  pending_question: any | null;
  documents: ReviewDocumentItem[];
  has_report: boolean;
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
