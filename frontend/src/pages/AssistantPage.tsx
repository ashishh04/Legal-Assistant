import { useSearchParams } from "react-router-dom";
import { Database, FileSearch, Languages, Quote, ShieldCheck } from "lucide-react";
import { Chat } from "../components/Chat";
import { Card } from "../components/ui";
import { useSession } from "../session";

const CAPABILITIES = [
  { icon: FileSearch, title: "Reads the case files", text: "Judgments, claims, letters, agreements, reports and notices from the SharePoint case libraries." },
  { icon: Database, title: "Knows the case tracker", text: "Status, deadlines, hearings, amounts and portfolio figures, the same data the dashboards show." },
  { icon: Quote, title: "Cites its sources", text: "Every statement from a document links to the exact paragraph it came from." },
  { icon: Languages, title: "English and Arabic", text: "Ask in either language, whatever language the document is in." },
  { icon: ShieldCheck, title: "Respects access", text: "It only sees the cases and documents the signed-in persona may open." },
];

export default function AssistantPage() {
  const [params] = useSearchParams();
  const { user } = useSession();
  const caseId = params.get("case")?.toUpperCase() ?? null;
  if (!user) return null;
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
      <Card className="flex h-[calc(100dvh-8.5rem)] min-h-[520px] flex-col overflow-hidden">
        <Chat key={`${user.user_id}-${caseId ?? "all"}`} caseId={caseId} />
      </Card>
      <aside className="hidden flex-col gap-4 xl:flex">
        <Card className="p-5">
          <div className="text-[12px] font-medium text-muted">Asking as</div>
          <div className="mt-1 text-[15px] font-semibold text-ink">{user.full_name}</div>
          <div className="text-[12.5px] text-ink-2">{user.job_title} · {user.entra_group}</div>
          <p className="mt-3 rounded-xl bg-surface-2 p-3 text-[12.5px] leading-relaxed text-ink-2">Can see {user.access}.</p>
        </Card>
        <Card className="p-5">
          <div className="mb-3 text-[12px] font-medium text-muted">What Ferrero can do</div>
          <ul className="space-y-3.5">
            {CAPABILITIES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent-ink"><Icon size={15} /></span>
                <span>
                  <span className="block text-[13px] font-medium text-ink">{title}</span>
                  <span className="block text-[12px] leading-relaxed text-ink-2">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </aside>
    </div>
  );
}
