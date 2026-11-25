import { useSearchParams } from "react-router-dom";
import { Database, FileSearch, Languages, Quote, ShieldCheck } from "lucide-react";
import { Chat } from "../components/Chat";
import { Avatar, Card, Chip } from "../components/ui";
import { useSession } from "../session";

const CAPABILITIES = [
  { icon: FileSearch, title: "Reads the case files", text: "Judgments, claims, letters, agreements, reports and notices from the SharePoint case libraries." },
  { icon: Database, title: "Knows the case tracker", text: "Status, deadlines, hearings, amounts and portfolio figures, the same data the dashboards show." },
  { icon: Quote, title: "Cites its sources", text: "Every statement from a document links to the exact paragraph it came from." },
  { icon: Languages, title: "English and Arabic", text: "Ask in either language, whatever language the document is in." },
  { icon: ShieldCheck, title: "Respects access", text: "It only sees the cases and documents the signed-in user may open." },
];

export default function AssistantPage() {
  const [params] = useSearchParams();
  const { user } = useSession();
  const caseId = params.get("case")?.toUpperCase() ?? null;
  if (!user) return null;
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_312px]">
      <div className="flex h-[calc(100dvh-8.5rem)] min-h-[520px] flex-col overflow-hidden rounded-xl border border-line bg-surface-2 shadow-card">
        <Chat key={`${user.user_id}-${caseId ?? "all"}`} caseId={caseId} />
      </div>
      <aside className="hidden flex-col gap-5 xl:flex">
        <Card className="p-5">
          <div className="text-[12.5px] font-medium text-muted">Asking as</div>
          <div className="mt-3 flex items-center gap-3">
            <Avatar name={user.full_name} size={40} />
            <div className="min-w-0">
              <div className="truncate text-[14.5px] font-semibold text-ink">{user.full_name}</div>
              <div className="truncate text-[12.5px] text-muted">{user.job_title}</div>
            </div>
          </div>
          <div className="mt-4 border-t border-line pt-3.5 text-[13px] leading-relaxed text-ink-2">
            <Chip tone="outline" className="me-1.5">{user.entra_group}</Chip>
            Can see {user.access}.
          </div>
        </Card>
        <Card className="p-5">
          <div className="mb-4 text-[12.5px] font-medium text-muted">What Ferrero can do</div>
          <ul className="space-y-4">
            {CAPABILITIES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3">
                <Icon size={17} strokeWidth={1.7} className="mt-0.5 shrink-0 text-accent" />
                <span>
                  <span className="block text-[13.5px] font-medium text-ink">{title}</span>
                  <span className="mt-0.5 block text-[12.5px] leading-relaxed text-muted">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </aside>
    </div>
  );
}
