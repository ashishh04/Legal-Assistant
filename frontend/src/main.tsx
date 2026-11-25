import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import "./index.css";
import { Monogram } from "./components/Brand";
import { Shell } from "./components/Shell";
import AdminUsers from "./pages/AdminUsers";
import AssistantPage from "./pages/AssistantPage";
import CaseDetail from "./pages/CaseDetail";
import Cases from "./pages/Cases";
import Dashboards from "./pages/Dashboards";
import Documents from "./pages/Documents";
import DocumentView from "./pages/DocumentView";
import FollowUps from "./pages/FollowUps";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Logout from "./pages/Logout";
import NotFound from "./pages/NotFound";
import Overview from "./pages/Overview";
import { ToastProvider } from "./lib/toast";
import { SessionProvider, useSession } from "./session";

/** The app for signed-in users; the landing page at "/" for everyone else, and sign-in for any other address. */
function Gate() {
  const { status, bootError } = useSession();
  const location = useLocation();
  if (bootError) return <Splash text="Ferrero is temporarily unavailable. Please refresh the page in a moment." />;
  if (status === "loading") return <Splash />;
  if (status === "signed-out") {
    const deepLink = new URLSearchParams(location.search).has("case");  // "Ask Ferrero" links from the dashboards
    if (location.pathname === "/" && !deepLink) return <Landing />;
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }
  return <Shell />;
}

function Splash({ text }: { text?: string }) {
  return (
    <div className="grid h-full place-items-center bg-page px-6">
      <div className="flex flex-col items-center gap-5 text-center">
        <Monogram size={52} />
        <p className="max-w-xs text-[14px] leading-relaxed text-muted" role="status">{text ?? "Loading…"}</p>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <ToastProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/logout" element={<Logout />} />
            <Route path="/" element={<Gate />}>
              <Route index element={<Overview />} />
              <Route path="cases" element={<Cases />} />
              <Route path="cases/:caseId" element={<CaseDetail />} />
              <Route path="follow-ups" element={<FollowUps />} />
              <Route path="assistant" element={<AssistantPage />} />
              <Route path="documents" element={<Documents />} />
              <Route path="documents/:docId" element={<DocumentView />} />
              <Route path="dashboards" element={<Dashboards />} />
              <Route path="admin/users" element={<AdminUsers />} />
              <Route path="home" element={<Navigate to="/" replace />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </ToastProvider>
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
