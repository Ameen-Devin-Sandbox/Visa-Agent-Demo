const BASE = '/api/v1';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

import type {
  HealthResponse,
  QueueStatsResponse,
  DisputeSummary,
  DisputeDetail,
  DisputeSubmitRequest,
  EvidenceInput,
} from './types';

export const api = {
  health: () => request<HealthResponse>('/health'),

  queueStats: () => request<QueueStatsResponse>('/queue/stats'),

  listDisputes: () => request<DisputeSummary[]>('/disputes'),

  getDispute: (id: string) => request<DisputeDetail>(`/disputes/${id}`),

  submitDispute: (data: DisputeSubmitRequest) =>
    request<DisputeSummary>('/disputes', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  submitReview: (id: string, approved: boolean, notes: string) =>
    request<DisputeSummary>(`/disputes/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ approved, reviewer_notes: notes }),
    }),

  escalatePreArbitration: (id: string, evidence: EvidenceInput[]) =>
    request<DisputeSummary>(`/disputes/${id}/pre-arbitration`, {
      method: 'POST',
      body: JSON.stringify({ acquirer_evidence: evidence }),
    }),

  escalateArbitration: (id: string) =>
    request<DisputeSummary>(`/disputes/${id}/arbitration`, {
      method: 'POST',
    }),

  addEvidence: (id: string, evidence: EvidenceInput) =>
    request<DisputeSummary>(`/disputes/${id}/evidence`, {
      method: 'POST',
      body: JSON.stringify(evidence),
    }),
};
