import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { Shell } from "./components/Shell";
import AssistantPage from "./pages/AssistantPage";
import CaseDetail from "./pages/CaseDetail";
import Cases from "./pages/Cases";
import Dashboards from "./pages/Dashboards";
import Documents from "./pages/Documents";
import DocumentView from "./pages/DocumentView";
import Overview from "./pages/Overview";
import { SessionProvider } from "./session";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Overview />} />
            <Route path="cases" element={<Cases />} />
            <Route path="cases/:caseId" element={<CaseDetail />} />
            <Route path="assistant" element={<AssistantPage />} />
            <Route path="documents" element={<Documents />} />
            <Route path="documents/:docId" element={<DocumentView />} />
            <Route path="dashboards" element={<Dashboards />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
