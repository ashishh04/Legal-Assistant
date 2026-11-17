/** Plain-language versions of the document sync's reasons (the raw reasons stay in the sync report). */
export function friendlyReason(reason: string | null | undefined): string {
  const r = reason ?? "";
  if (!r) return "";
  if (r.startsWith("Scanned PDF – waiting")) return "Text recognition pending";
  if (r.startsWith("Scanned PDF – ")) return "The scan's pages could not be read";
  if (r.startsWith("OCR confidence below threshold")) return "Scan too faint to read reliably";
  if (r.startsWith("Low-confidence pages flagged for review")) {
    const pages = r.match(/\((pages? [^)]+)\)/)?.[1];
    return pages ? `Check ${pages} against the scan` : "Some pages need a check against the scan";
  }
  if (r.startsWith("Password")) return "Never opened";
  if (r.startsWith("Duplicate of")) return r;
  if (r.startsWith("Content does not match")) return "Content doesn't match the linked case";
  if (r.startsWith("File name refers")) return "File name and content refer to different cases";
  if (r.startsWith("The text refers to several cases")) return "Refers to more than one case";
  if (r.includes("not in the case tracker")) return "Case number not found";
  if (r.startsWith("No case number") || r.startsWith("No matching case")) return "Not linked to a case";
  if (r.startsWith("Queued")) return "Queued for processing";
  if (r.startsWith("Unreadable")) return "File could not be read";
  if (r.startsWith("Unsupported file type")) return "File type not supported";
  if (r.startsWith("Arabic PDF text layer")) return "Text extracted – figures to be checked against the original";
  return r;
}

/** "94%" for a 0–1 recognition confidence. */
export function pct(value: number | null | undefined): string {
  return value == null ? "–" : `${Math.round(value * 100)}%`;
}

/** Audit-trail actions in plain language. */
export const AUDIT_ACTIONS: Record<string, string> = {
  "case.registered": "Case registered",
  "case.updated": "Case updated",
  "case.closed": "Case closed",
  "case.reopened": "Case reopened",
  "business.updated": "Business assessment updated",
  "business.override": "Enforcement without business clearance",
  "evidence.added": "Evidence added",
  "evidence.updated": "Evidence details changed",
  "evidence.withdrawn": "Evidence withdrawn",
  "follow_up.created": "Follow-up set",
  "follow_up.updated": "Follow-up changed",
  "follow_up.extended": "Deadline extended",
  "follow_up.resolved": "Follow-up resolved",
  "comparison.recorded": "Trademark comparison recorded",
};

/** Where a deadline stands, against the reporting date. */
export function deadlineState(daysLeft: number, leadDays = 7): "overdue" | "today" | "soon" | "later" {
  if (daysLeft < 0) return "overdue";
  if (daysLeft === 0) return "today";
  return daysLeft <= leadDays ? "soon" : "later";
}
