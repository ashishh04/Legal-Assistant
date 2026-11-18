import type {
  AdminUser, AdminUsers, AuditChange, AuditTrail, CaseChanges, CaseDetail, CaseRow, ComparisonData, ComparisonInput, ConversationInfo,
  DashboardsInfo, DocumentView, EvidenceDetails, EvidenceItem, FollowUp, FollowUpDecision, MarkInfo, Me, Meta, NewCase,
  NewFollowUp, NewUser, Notifications, Overview, PublicInfo, RegisterOptions, SimilarityResult, StreamEvent, SyncStatus, User,
  Worklist,
} from "./types";

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string) {
    super(message);
  }
}

/** Sent with every request: the server refuses changes without it, so other sites can't act with the user's cookie. */
const APP_HEADER = { "X-Ferrero": "1" };

function apiError(body: { detail?: unknown; code?: unknown }, status: number, fallback: string): ApiError {
  return new ApiError(typeof body.detail === "string" ? body.detail : fallback, status,
    typeof body.code === "string" ? body.code : undefined);
}

/** A request answered 401: the session ended (signed out elsewhere, expired, password changed). */
function sessionEnded(path: string) {
  if (!path.startsWith("/api/auth/")) window.dispatchEvent(new Event("ferrero:signed-out"));
}

async function request<T>(path: string, init?: RequestInit, params?: Record<string, string | null | undefined>): Promise<T> {
  const url = new URL(path, window.location.origin);
  for (const [k, v] of Object.entries(params ?? {})) if (v) url.searchParams.set(k, v);
  const res = await fetch(url, { ...init, headers: { "Content-Type": "application/json", ...APP_HEADER, ...init?.headers } });
  if (!res.ok) {
    if (res.status === 401) sessionEnded(path);
    const body = await res.json().catch(() => ({}));
    throw apiError(body, res.status, res.statusText);
  }
  return res.json() as Promise<T>;
}

const send = <T>(method: string, path: string, body: unknown) => request<T>(path, { method, body: JSON.stringify(body) });
const enc = encodeURIComponent;

/** Tell the rest of the page (the notification bell, open lists) that case records changed. */
export const recordsChanged = () => window.dispatchEvent(new Event("ferrero:records"));

export const api = {
  // ---------- signing in ----------
  publicInfo: () => request<PublicInfo>("/api/public"),
  me: async () => (await request<{ user: Me | null }>("/api/auth/me")).user,
  login: async (login: string, password: string, remember: boolean) =>
    (await send<{ user: Me }>("POST", "/api/auth/login", { login, password, remember })).user,
  logout: () => send<{ signed_out: boolean }>("POST", "/api/auth/logout", {}),
  changePassword: (currentPassword: string, newPassword: string) =>
    send<{ changed: boolean }>("POST", "/api/auth/password", { current_password: currentPassword, new_password: newPassword }),

  // ---------- the platform administrator ----------
  adminUsers: () => request<AdminUsers>("/api/admin/users"),
  addUser: (data: NewUser) => send<AdminUser>("POST", "/api/admin/users", data),
  updateUser: (userId: string, changes: Partial<Pick<AdminUser, "full_name" | "job_title" | "entra_group" | "country" | "active">>) =>
    send<AdminUser>("PATCH", `/api/admin/users/${enc(userId)}`, { changes }),
  setUserPassword: (userId: string, password: string) =>
    send<AdminUser>("POST", `/api/admin/users/${enc(userId)}/password`, { password }),
  switchUser: async (userId: string) => (await send<{ user: Me }>("POST", "/api/admin/switch", { user_id: userId })).user,
  switchBack: async () => (await send<{ user: Me }>("POST", "/api/admin/switch/back", {})).user,

  // ---------- the app ----------
  meta: () => request<Meta>("/api/meta"),
  users: () => request<User[]>("/api/users"),
  overview: (country?: string, mark?: string) => request<Overview>("/api/overview", undefined, { country, mark }),
  cases: () => request<CaseRow[]>("/api/cases"),
  case: (caseId: string) => request<CaseDetail>(`/api/cases/${enc(caseId)}`),
  sync: () => request<SyncStatus>("/api/sync"),
  document: (docId: string) => request<DocumentView>(`/api/documents/${enc(docId)}`),
  pageImageUrl: (docId: string, page: number) => `/api/documents/${enc(docId)}/pages/${page}`,
  startConversation: (caseId?: string | null) => send<ConversationInfo>("POST", "/api/conversations", { case_id: caseId || null }),
  dashboards: () => request<DashboardsInfo>("/api/dashboards"),
  guestToken: async (dashboard: string, caseId?: string | null) =>
    (await send<{ token: string }>("POST", "/api/dashboards/guest-token", { dashboard, case_id: caseId || null })).token,

  // ---------- case records: changes, evidence, follow-ups, notifications, audit trail ----------
  updateCase: (caseId: string, changes: CaseChanges, reason?: string, overrideReason?: string) =>
    send<{ changes: AuditChange[]; case: CaseDetail }>("PATCH", `/api/cases/${enc(caseId)}`,
      { changes, reason: reason || null, override_reason: overrideReason || null }),
  audit: (caseId: string) => request<AuditTrail>(`/api/cases/${enc(caseId)}/audit`),
  auditCsvUrl: (caseId: string) => `/api/cases/${enc(caseId)}/audit.csv`,
  evidence: (caseId: string) => request<EvidenceItem[]>(`/api/cases/${enc(caseId)}/evidence`),
  evidenceFileUrl: (evidenceId: string, download = false) =>
    `/api/evidence/${enc(evidenceId)}/file${download ? "?download=true" : ""}`,
  updateEvidence: (evidenceId: string, changes: Partial<EvidenceDetails>, reason?: string) =>
    send<EvidenceItem>("PATCH", `/api/evidence/${enc(evidenceId)}`, { changes, reason: reason || null }),
  withdrawEvidence: (evidenceId: string, reason: string) =>
    send<EvidenceItem>("POST", `/api/evidence/${enc(evidenceId)}/withdraw`, { reason }),
  verifyEvidence: (evidenceId: string) =>
    request<{ ok: boolean; sha256: string; checked_at: string }>(`/api/evidence/${enc(evidenceId)}/verify`),
  followUps: (caseId: string) => request<FollowUp[]>(`/api/cases/${enc(caseId)}/follow-ups`),
  createFollowUp: (caseId: string, data: NewFollowUp) => send<FollowUp>("POST", `/api/cases/${enc(caseId)}/follow-ups`, data),
  updateFollowUp: (followUpId: string, changes: Record<string, unknown>, reason?: string) =>
    send<FollowUp>("PATCH", `/api/follow-ups/${enc(followUpId)}`, { changes, reason: reason || null }),
  resolveFollowUp: (followUpId: string, data: FollowUpDecision) =>
    send<FollowUp>("POST", `/api/follow-ups/${enc(followUpId)}/resolve`, data),
  worklist: () => request<Worklist>("/api/follow-ups"),
  registerOptions: () => request<RegisterOptions>("/api/register/options"),
  registerCase: (data: NewCase) => send<{ case_id: string; case: CaseDetail }>("POST", "/api/cases", data),

  // ---------- registered marks and the visual trademark comparison ----------
  marks: () => request<MarkInfo[]>("/api/marks"),
  markSpecimenUrl: (markId: string) => `/api/marks/${enc(markId)}/specimen`,
  similarity: (markId: string, sign: string) =>
    request<SimilarityResult>(`/api/marks/${enc(markId)}/similarity`, undefined, { sign }),
  comparison: (caseId: string) => request<ComparisonData>(`/api/cases/${enc(caseId)}/comparison`),
  recordComparison: (caseId: string, data: ComparisonInput) =>
    send<ComparisonData>("POST", `/api/cases/${enc(caseId)}/comparison`, data),
  notifications: () => request<Notifications>("/api/notifications"),
  markRead: (ids?: number[]) => send<{ marked: number }>("POST", "/api/notifications/read", { ids: ids ?? null }),
};

/** Upload one evidence file as the request body, reporting progress (0–1). */
export function uploadEvidence(caseId: string, file: File, details: EvidenceDetails,
  onProgress?: (fraction: number) => void): Promise<EvidenceItem> {
  return new Promise((resolve, reject) => {
    const url = new URL(`/api/cases/${enc(caseId)}/evidence`, window.location.origin);
    url.searchParams.set("file_name", file.name);
    for (const [k, v] of Object.entries(details)) if (v) url.searchParams.set(k, String(v));
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
    xhr.setRequestHeader("X-Ferrero", "1");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress?.(e.loaded / e.total); };
    xhr.onload = () => {
      let body: { detail?: unknown; code?: unknown } = {};
      try { body = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as unknown as EvidenceItem);
      else {
        if (xhr.status === 401) sessionEnded(url.pathname);
        reject(apiError(body, xhr.status, xhr.status === 413 ? "The file is too large." : "The upload failed."));
      }
    };
    xhr.onerror = () => reject(new ApiError("The upload was interrupted. Check the connection and try again.", 0));
    xhr.send(file);
  });
}

/** Send one message and yield the server-sent events: tool steps, then the answer (or an error), then done. */
export async function* streamMessage(conversationId: string, text: string, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  const res = await fetch(`/api/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...APP_HEADER },
    body: JSON.stringify({ text }),
    signal,
  });
  if (!res.ok || !res.body) {
    if (res.status === 401) sessionEnded("/api/conversations");
    const body = await res.json().catch(() => ({}));
    throw apiError(body, res.status, res.statusText);
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
