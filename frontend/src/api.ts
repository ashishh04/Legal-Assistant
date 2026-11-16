import type {
  CaseDetail, CaseRow, ConversationInfo, DashboardsInfo, DocumentView, Meta, Overview, StreamEvent, SyncStatus, User,
} from "./types";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit, params?: Record<string, string | null | undefined>): Promise<T> {
  const url = new URL(path, window.location.origin);
  for (const [k, v] of Object.entries(params ?? {})) if (v) url.searchParams.set(k, v);
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(typeof body.detail === "string" ? body.detail : res.statusText, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => request<Meta>("/api/meta"),
  users: () => request<User[]>("/api/users"),
  overview: (userId: string, country?: string, mark?: string) =>
    request<Overview>("/api/overview", undefined, { user_id: userId, country, mark }),
  cases: (userId: string) => request<CaseRow[]>("/api/cases", undefined, { user_id: userId }),
  case: (userId: string, caseId: string) =>
    request<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`, undefined, { user_id: userId }),
  sync: (userId: string) => request<SyncStatus>("/api/sync", undefined, { user_id: userId }),
  document: (userId: string, docId: string) =>
    request<DocumentView>(`/api/documents/${encodeURIComponent(docId)}`, undefined, { user_id: userId }),
  pageImageUrl: (userId: string, docId: string, page: number) =>
    `/api/documents/${encodeURIComponent(docId)}/pages/${page}?user_id=${encodeURIComponent(userId)}`,
  startConversation: (userId: string, caseId?: string | null) =>
    request<ConversationInfo>("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, case_id: caseId || null }),
    }),
  dashboards: (userId: string) => request<DashboardsInfo>("/api/dashboards", undefined, { user_id: userId }),
  guestToken: async (userId: string, dashboard: string, caseId?: string | null) =>
    (await request<{ token: string }>("/api/dashboards/guest-token", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, dashboard, case_id: caseId || null }),
    })).token,
};

/** Send one message and yield the server-sent events: tool steps, then the answer (or an error), then done. */
export async function* streamMessage(conversationId: string, text: string, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  const res = await fetch(`/api/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
    signal,
  });
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(typeof body.detail === "string" ? body.detail : res.statusText, res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      if (chunk.startsWith("data: ")) yield JSON.parse(chunk.slice(6)) as StreamEvent;
    }
  }
}
