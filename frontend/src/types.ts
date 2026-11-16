export interface User {
  user_id: string;
  full_name: string;
  job_title: string;
  team: string;
  country: string;
  entra_group: string;
  access: string;
  documents: boolean;
}

export interface Meta {
  model: string;
  effort: string;
  provider: string;
  demo_today: string;
  org_name: string;
  index: { documents: number; indexed: number; passages: number };
  examples: string[];
  dashboards: { title: string; url: string }[];
  embedded_dashboards?: boolean;
}

/** A dashboard Ferrero embeds through the dashboard server's SDK, with a guest token per persona. */
export interface EmbeddedDashboardInfo {
  code: string | null;
  title: string;
  full_title: string;
  uuid: string;
  url: string;
  allowed_domains: string[];
}

export interface DashboardsInfo {
  mode: "embedded" | "links" | "none";
  superset_url?: string;
  frame_ancestors?: string[] | null;
  dashboards: EmbeddedDashboardInfo[] | { title: string; url: string }[];
  error?: string;
}

export interface Kpis {
  cases: number;
  open_cases: number;
  new_cases_30d: number;
  hearings_30d: number;
  overdue_actions: number;
  avg_days_open: number | null;
  closed_ytd: number;
  claimed: number;
  awarded: number;
  settled: number;
  recovered: number;
  favourable: number;
  decided: number;
  legal_spend: number;
  recovery_rate: number | null;
  win_rate: number | null;
  spend_to_recovery: number | null;
}

export interface LabelValue {
  label: string;
  value: number;
}

export interface YearAmounts {
  year: string;
  claimed: number;
  awarded_or_settled: number;
  recovered: number;
}

export interface UpcomingRow {
  case_id: string;
  title: string;
  country: string;
  court_name: string;
  stage: string;
  next_hearing_date: string | null;
  next_action: string | null;
  next_action_due: string | null;
  lead_counsel: string;
  overdue: number;
}

export interface InfringerRow {
  infringer_id: string;
  name: string;
  type: string;
  country: string;
  cases: number;
  open: number;
  recovered: number;
}

export interface Overview {
  as_of: string;
  kpis: Kpis;
  open_by_stage: LabelValue[];
  open_by_country: LabelValue[];
  amounts_by_year: YearAmounts[];
  outcomes: LabelValue[];
  upcoming: UpcomingRow[];
  top_infringers: InfringerRow[];
  opened_by_month: { month: string; value: number }[];
  filters: { countries: string[]; marks: { id: string; name: string }[] };
}

export interface CaseRow {
  case_id: string;
  title: string;
  mark_id: string;
  mark_name: string;
  infringer_name: string;
  infringer_type: string;
  case_type: string;
  country: string;
  court_name: string;
  status: "Open" | "Closed";
  stage: string;
  outcome: string;
  priority: string;
  risk_rating: string | null;
  opened_date: string;
  closed_date: string | null;
  next_hearing_date: string | null;
  next_action: string | null;
  next_action_due: string | null;
  lead_counsel: string;
  currency: string;
  claim_amount_aed: number;
  awarded_amount_aed: number;
  settlement_amount_aed: number;
  recovered_amount_aed: number;
  days_open: number;
  overdue: number;
}

export interface TimelineEvent {
  event_date: string;
  event_type: string;
  external_fees_aed: number;
}

export interface CaseDocument {
  doc_id?: string;
  synced_doc_id?: string;
  title?: string;
  file_name?: string;
  doc_type: string | null;
  language: string | null;
  doc_date?: string | null;
  text_searchable: boolean;
  scanned_copy?: boolean;
  ocr_confidence?: number;
  sync_note?: string;
  review_note?: string;
}

export interface CaseDetail {
  case_id: string;
  title: string;
  case_type: string;
  country: string;
  court_name: string;
  status: "Open" | "Closed";
  stage: string;
  outcome: string;
  opened_date: string;
  closed_date: string | null;
  priority: string;
  risk_rating: string | null;
  mark_name: string;
  infringer_name: string;
  infringer_type: string;
  lead_counsel: string;
  external_firm: string | null;
  source_channel: string;
  currency: string;
  claim_amount_local: number;
  claim_amount_aed: number;
  awarded_amount_local: number;
  awarded_amount_aed: number;
  settlement_amount_local: number;
  settlement_amount_aed: number;
  recovered_amount_local: number;
  recovered_amount_aed: number;
  next_hearing_date: string | null;
  next_action: string | null;
  next_action_due: string | null;
  last_action_date: string | null;
  days_open: number;
  language: string;
  sensitivity: string;
  timeline: TimelineEvent[];
  invoices: { count: number; total_aed: number; by_category_aed: Record<string, number> };
  documents_on_file: CaseDocument[] | string;
}

export interface SyncDoc {
  doc_id: string;
  case_id: string;
  file_name: string;
  doc_type: string | null;
  language: string | null;
  access_group: string;
  sensitivity: string | null;
  library_path: string;
  extraction: "text" | "ocr" | null;
  ocr_confidence: number | null;
  pages: number | null;
  index_status: string;
  skip_reason: string | null;
  passages: number;
  indexed_at: string;
}

export interface DocumentSection {
  section: string;
  seq: number;
  blocks: string[];
}

export interface DocumentView {
  doc_id: string;
  file_name: string;
  case_id: string;
  doc_type: string | null;
  language: string | null;
  access_group: string;
  sensitivity: string | null;
  library_path: string;
  index_status: string;
  skip_reason: string | null;
  extraction: "text" | "ocr" | null;
  ocr_confidence: number | null;
  pages: number | null;
  sections: DocumentSection[];
  page_images: number;
  page_confidence: (number | null)[];
  review_confidence?: number;
}

export interface SyncStatus {
  documents: SyncDoc[];
  counts: Record<string, number>;
  visible: boolean;
}

export interface Citation {
  n: number;
  source: string;
  title: string;
  cited_text: string;
  file_name?: string;
  doc_id?: string;
  section?: string;
  doc_type?: string | null;
  library_path?: string;
  case_id?: string;
  language?: string | null;
  scanned?: boolean;
}

export interface ToolStep {
  name: string;
  input: Record<string, unknown>;
  summary?: string;
  is_error?: boolean;
}

export interface Answer {
  text: string;
  segments: { text: string; citations: number[] }[];
  citations: Citation[];
  tools: ToolStep[];
  route: string[];
  stop_reason: string;
  model: string | null;
  usage: Record<string, number>;
  latency_s: number;
}

export interface ConversationInfo {
  conversation_id: string;
  user: { user_id: string; full_name: string; job_title: string; entra_group: string; access: string; documents: boolean };
  case: { case_id: string; title: string; status: string; stage: string; outcome: string; court_name: string } | null;
  case_requested: string | null;
}

export type StreamEvent =
  | { type: "tool"; name: string; input: Record<string, unknown> }
  | ({ type: "answer" } & Answer)
  | { type: "error"; message: string }
  | { type: "done" };
