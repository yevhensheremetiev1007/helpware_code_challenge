const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8080";

export const TENANT = "acme";

export type QueueItem = {
  id: string;
  conversation_id: string;
  total: number;
  created_at: string;
};

export type Score = {
  id: string;
  conversation_id: string;
  rubric_version_id: string;
  total: number;
  model_id: string;
  prompt_hash: string;
  created_at: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      "X-Tenant-Slug": TENANT,
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export const getQueue = (limit: number, offset: number) =>
  request<QueueItem[]>(`/v1/queue?limit=${limit}&offset=${offset}`);

export const getScores = (conversationId: string) =>
  request<Score[]>(`/v1/conversations/${conversationId}/scores`);

export const rescore = (conversationId: string) =>
  request<Score>(`/v1/conversations/${conversationId}/score`, {
    method: "POST",
    body: JSON.stringify({ priority: "interactive" }),
  });
