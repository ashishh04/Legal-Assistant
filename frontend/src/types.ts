export interface User {
  user_id: string;
  full_name: string;
  job_title: string;
  team: string;
  country: string;
  entra_group: string;
  access: string;
  documents: boolean;
  can_edit: boolean;
  case_groups: string[];
  active?: boolean;   // false: disabled by the administrator
  can_own?: boolean;  // may own cases and follow-ups
  admin?: boolean;    // the platform administrator
}

/** The signed-in user: a directory entry plus the sign-in details. */
export interface Me extends User {
  email: string;
  own_password: boolean; // false: still on a starting or temporary password
  is_admin?: boolean;
  /** Set while the platform administrator views the portal as this user. */
  acting_by?: { user_id: string; full_name: string } | null;
}

/** An account as the administrator's Users page shows it. */
export interface AdminUser {
  user_id: string;
  full_name: string;
  job_title: string;
  team: string;
  country: string;
  entra_group: string;
  email: string;
  source: "directory" | "added" | "administrator";
  active: boolean;
  password: "configured" | "own" | "temporary" | "starting" | "not set";
  access: string;
  last_sign_in: string | null;
}

export interface AdminUsers {
  users: AdminUser[];
  roles: { group: string; description: string }[];
  countries: string[];
  starting_password: boolean;
}

export interface NewUser {
  full_name: string;
  email: string;
  job_title: string;
  entra_group: string;
  country: string;
  password: string;
}

/** What the landing and sign-in pages get before anyone signs in. */
export interface PublicInfo {
  org_name: string;
  sign_in_configured: boolean;
  accounts: { user_id: string; full_name: string; job_title: string; entra_group: string; email: string }[] | null;
}

export type Decision = "close_case" | "keep_open" | "escalate" | "cancel";

/** Choices for the case forms (case fields, evidence, follow-ups), from /api/meta. */
export interface CaseOptions {
  stages_open: string[];
  stages_closed: string[];
  outcomes: string[];
  levels: string[];
  relationships: string[];
  consultation_statuses: string[];
  enforcement_stages: string[];
  labels: Record<string, string>;
  evidence_categories: string[];
  photo_categories: string[];
  accept: string;
  accepted_types: string;
  evidence_max_mb: number;
  follow_up_kinds: { kind: string; title: string; days: number }[];
  decisions: { value: Decision; label: string }[];
  reminder_lead_days: number;
  escalate_days: number;
  comparison: { similarity: string[]; goods: string[]; overall: string[]; labels: Record<string, string> };
}

export interface Meta {
  model: string;
  effort: string;
  provider: string;
  /** The date the app works to ("today" for deadlines and forms): the real date, unless the server fixes one. */
  demo_today: string;
  /** Whether the server works to a fixed date (a demonstration) rather than the calendar. */
  today_fixed?: boolean;
  org_name: string;
  index: { documents: number; indexed: number; passages: number };
  examples: string[];
  dashboards: { title: string; url: string }[];
  embedded_dashboards?: boolean;
  case_options: CaseOptions;
  email_notifications: boolean;
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
  lead_counsel_id: string;
  business_priority: string | null;
  consultation_required: number | null;
  consultation_status: string | null;
  commercial_relationship: string | null;
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
  mark_id: string;
  infringer_id: string;
  case_type: string;
  country: string;
  court_name: string | null;
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
  access_group: string;
  lead_counsel_id: string;
  business_priority: string | null;
  consultation_required: boolean | null;
  commercial_relationship: string | null;
  consultation_status: string | null;
  consultation_contact: string | null;
  consultation_notes: string | null;
  timeline: TimelineEvent[];
  invoices: { count: number; total_aed: number; by_category_aed: Record<string, number> };
  documents_on_file: CaseDocument[] | string;
  follow_ups: { follow_up_id: string; kind: string; title: string; owner_name: string; due_date: string; status: string; decision: string | null }[];
  mark_comparison: ComparisonEntry | null;
  registered_in_app: boolean;
  permissions: { edit: boolean; evidence: boolean; add_evidence: boolean };
  counts: { evidence: number | null; follow_ups_open: number; audit: number };
}

/** Choices for registering a case (GET /api/register/options), limited to the countries the user covers. */
export interface RegisterOptions {
  marks: { mark_id: string; mark_name: string; mark_name_ar: string; product_category: string }[];
  case_types: string[];
  sources: string[];
  countries: { country: string; currency: string; access_group: string }[];
  courts: { court_id: string; country: string; court_name: string }[];
  infringers: { infringer_id: string; name: string; name_ar: string | null; type: string; country: string }[];
  infringer_types: string[];
  levels: string[];
  relationships: string[];
  languages: string[];
  sensitivities: string[];
  default_next_action: string;
  default_next_action_days: number;
}

/** A new case (POST /api/cases). */
export interface NewCase {
  mark_id: string;
  infringer_id?: string | null;
  infringer_name?: string | null;
  infringer_type?: string | null;
  infringer_city?: string | null;
  case_type: string;
  country: string;
  court_id?: string | null;
  source_channel: string;
  opened_date?: string | null;
  priority: string;
  risk_rating?: string | null;
  lead_counsel_id?: string | null;
  external_firm?: string | null;
  next_action?: string | null;
  next_action_due?: string | null;
  claim_amount_local?: number | null;
  language?: string | null;
  sensitivity?: string | null;
  business_priority?: string | null;
  consultation_required?: boolean | null;
  commercial_relationship?: string | null;
  details?: string | null;
}

/** A registered mark, as the comparison shows it. */
export interface MarkInfo {
  mark_id: string;
  mark_name: string;
  mark_name_ar: string;
  product_category: string;
  nice_classes: string;
  registration_no: string;
  registered_in: string[];
  specimen: boolean;
}

/** Indicative similarity between a mark and a sign (an aid, not a finding). */
export interface SimilarityResult {
  compared_with: string;
  word_similarity: number | null;
  letters_different: number | null;
  sounds_alike: boolean;
  contains_mark: boolean;
  identical?: boolean;
  indication: "High" | "Medium" | "Low" | null;
}

export interface ComparisonEntry {
  comparison_id: string;
  evidence_id: string | null;
  infringing_sign: string;
  visual: string;
  phonetic: string;
  conceptual: string;
  goods: string;
  overall: string;
  notes: string | null;
  word_similarity: number | null;
  sounds_alike?: boolean | null;
  assessed_by: string;
  assessed_by_id?: string;
  assessed_at: string;
  status?: "Current" | "Superseded";
}

export interface ComparisonData {
  case_id: string;
  mark: MarkInfo | null;
  current: ComparisonEntry | null;
  history: ComparisonEntry[];
  indicators: SimilarityResult | null;
  photos: EvidenceItem[] | null;
  can_record: boolean;
}

export interface ComparisonInput {
  infringing_sign: string;
  evidence_id: string | null;
  visual: string;
  phonetic: string;
  conceptual: string;
  goods: string;
  overall: string;
  notes: string | null;
}

/** Editable case fields (PATCH /api/cases/:id). */
export type CaseChanges = Partial<Record<
  "status" | "stage" | "outcome" | "closed_date" | "priority" | "risk_rating" | "lead_counsel_id" | "external_firm" |
  "next_action" | "next_action_due" | "next_hearing_date" | "business_priority" | "commercial_relationship" |
  "consultation_status" | "consultation_contact" | "consultation_notes", string | null> & { consultation_required: boolean | null }>;

export interface EvidenceItem {
  evidence_id: string;
  case_id: string;
  category: string;
  title: string;
  notes: string | null;
  captured_on: string | null;
  location: string | null;
  file_name: string;
  content_type: string;
  file_label: string;
  image: boolean;
  size_bytes: number;
  sha256: string;
  uploaded_by_id: string;
  uploaded_by: string;
  uploaded_at: string;
  status: "Active" | "Withdrawn";
  withdrawn_by: string | null;
  withdrawn_at: string | null;
  withdrawn_reason: string | null;
}

export interface EvidenceDetails {
  category: string;
  title?: string;
  captured_on?: string;
  location?: string;
  notes?: string;
}

export interface FollowUp {
  follow_up_id: string;
  case_id: string;
  case_title?: string;
  kind: string;
  title: string;
  details: string | null;
  owner_id: string;
  owner_name: string;
  start_date: string;
  period_days: number | null;
  due_date: string;
  remind_days: number;
  status: "Open" | "Done" | "Cancelled";
  decision: string | null;
  decision_label: string | null;
  decision_note: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_by_id: string;
  created_by: string;
  created_at: string;
  days_left: number;
}

export interface NewFollowUp {
  kind: string;
  title: string;
  details?: string;
  owner_id?: string;
  start_date?: string;
  period_days?: number | null;
  due_date?: string;
  remind_days?: number;
}

export interface FollowUpDecision {
  decision: Decision;
  note?: string;
  outcome?: string;
  closed_date?: string;
  case_changes?: { stage?: string; next_action?: string; next_action_due?: string };
  override_reason?: string;
}

/** One open deadline on the worklist: a follow-up, a case's next action, or a hearing. */
export interface WorkItem {
  type: "follow_up" | "next_action" | "hearing";
  id: string;
  case_id: string;
  case_title?: string;
  kind: string;
  title: string;
  due_date: string;
  days_left: number;
  owner_id: string;
  owner_name: string;
  mine: boolean;
  status: string;
  link: string;
  decision_label?: string | null;
  decision_note?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
}

export interface Worklist {
  as_of: string;
  lead_days: number;
  escalate_days: number;
  items: WorkItem[];
  resolved: WorkItem[];
}

export interface NotificationItem {
  id: number;
  case_id: string;
  kind: "follow_up" | "next_action" | "hearing" | "assigned";
  stage: "upcoming" | "due" | "overdue" | "today" | "assigned";
  title: string;
  body: string;
  link: string;
  ref_id: string | null;
  due_date: string | null;
  days_left: number | null;
  created_at: string;
  read: boolean;
}

export interface Notifications {
  unread: number;
  items: NotificationItem[];
  email: boolean;
}

export interface AuditChange {
  field: string;
  label: string;
  old: unknown;
  new: unknown;
}

export interface AuditEntry {
  entry_id: string;
  at: string;
  actor_id: string;
  actor_name: string;
  actor_role: string;
  action: string;
  summary: string;
  changes: AuditChange[];
  reason: string | null;
  ref_type: string | null;
  ref_id: string | null;
  entry_hash: string;
}

export interface AuditTrail {
  entries: AuditEntry[];
  integrity: { ok: boolean; entries: number; head?: string; first_bad?: string; problem?: string };
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
