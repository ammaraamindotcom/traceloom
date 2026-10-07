import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { SecurityProvider } from "./context/SecurityContext";
import { ActivityPage } from "./pages/ActivityPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { PolicyPage } from "./pages/PolicyPage";

export default function App() {
  return <BrowserRouter><SecurityProvider><AppShell><Routes>
    <Route path="/overview" element={<OverviewPage />} />
    <Route path="/activity" element={<ActivityPage />} />
    <Route path="/incidents" element={<IncidentsPage />} />
    <Route path="/incidents/:userId" element={<IncidentDetailPage />} />
    <Route path="/policy" element={<PolicyPage />} />
    <Route path="/evaluation" element={<EvaluationPage />} />
    <Route path="*" element={<Navigate to="/overview" replace />} />
  </Routes></AppShell></SecurityProvider></BrowserRouter>;
}
